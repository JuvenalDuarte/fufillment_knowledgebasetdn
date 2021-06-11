def get_custom_log(parameters):
  # Cria os logs customizados a partir do parâmetros.
  # Custom logs são usadas na análise dos erros e criação das métricas
  import copy
  import json
  
  custom_log = copy.deepcopy(parameters)
  # Removemos parâmetros que não são pertinentes.
  custom_log.pop('user_ip_addr', None)
  custom_log.pop('a', None)
  custom_log.pop('formatted_help', None)
  custom_log.pop('list_help', None)
  custom_log.pop('session_log', None)
  custom_log.pop('preventDefault', None)
  custom_log = json.dumps(custom_log)
  return custom_log

def remove_punctuation(sentence):
  import string
  table = str.maketrans(dict.fromkeys(string.punctuation))
  return sentence.translate(table)  


def get_n_grams(sentence, N=2):
  # Função que cria n grams de uma sentença.
  # Os n grams são criados em minúsculo e sem caracteres especiais.
  # O default são bigrams (N=2): combinações de duas palavras.
  # Os ngrams são juntados por espaço e underline para podermos dar match
  # com as tags do artigos.
  from unidecode import unidecode
  sentence = remove_punctuation(unidecode(sentence.lower()))
  sentence = sentence.split()
  n_grams_arr = [sentence[i:i+N] for i in range(len(sentence)-N+1)]
  n_grams = [' '.join(n_gram) for n_gram in n_grams_arr]
  n_grams.extend(['_'.join(n_gram) for n_gram in n_grams_arr])
  return n_grams

def resize_images(answer):
  # Define o tamanho das imagens para que possam ser exibidas propriamente na janela de conversação.
  import re
  matches = re.finditer('<img(.*?)>', answer, re.IGNORECASE)
  for match in matches:
    match_content = match.group()
    url = re.search('(src=")(.*?)(")', match.group(1).strip()).group(2)
    answer = re.sub(re.escape(match_content), f'<img src={url} width="266" height="auto">', answer)
  return answer

def resize_videos(answer):
  # Define o tamanho dos vídeos para que possam ser exibidos propriamente na janela de conversação.
  import re
  matches = re.finditer('<iframe(.*?)>', answer, re.IGNORECASE)
  for match in matches:
    match_content = match.group()
    url = re.search('(src=")(.*?)(")', match.group(1).strip()).group(2)
    answer = re.sub(re.escape(match_content), f'<iframe src={url} width="266" height="auto">', answer)
  return answer

def open_url_in_new_tab(answer):
  import re
  answer = re.sub(r"\\s", re.escape(r" "), answer)
  answer = answer.replace('target="_self"', 'target="_blank"')
  answer = answer.replace('rel="undefined""', 'rel="noopener"')
  matches = re.finditer('<a\s(.*?)<\/a>', answer, re.IGNORECASE)
  for match in matches:
    match_content = match.group()
    if 'target="_blank" rel="noopener"' not in match_content:
      answer = re.sub(re.escape(match_content), f'<a target="_blank" rel="noopener" {match_content}</a>', answer)
  return answer

def get_answer(best_match, results, url_best_match, title_best_match, elasticsearch=False, k=3):
  # Montamos a resposta para o usuário a partir dos resultados do modelo ou elasticsearch

  # Coletamos a solução do melhor match
  answer = best_match.get('solution')
  # Redefinimos os tamanhos das imagens e vídeos da solução
  answer = resize_images(answer)
  answer = resize_videos(answer)
  answer = open_url_in_new_tab(answer)
  # Coletamos a URL e o nome da seção do melhor match
  section_url = best_match.get('section_html_url')
  section = best_match.get('section')
  # Pegamos a solução limpa de tags HTML. A solução limpa é usada nos tickets de log.
  if elasticsearch:
    sanitized_answer = best_match['sanitizedsolution'] + f'\n\nURL: {url_best_match}'
  else:
    sanitized_answer = best_match['sanitized_solution'] + f'\n\nURL: {url_best_match}'
  target = '_blank'
  # Adicionamos ao início da resposta o título do artigo de melhor match com sua respectiva URL de acesso
  answer = f'<br><b><a target="{target}" rel="noopener noreferrer" href="{url_best_match}" style="text-decoration: underline"><strong>{title_best_match}</strong></a></b><br>' + answer
  # Se houverem mais artigos nos resultados criamos a seção Saiba mais com o título de cada artigo
  # e suas respectivas URLs de acesso
  url_list = []
  if not elasticsearch:
    url_list.append(best_match.get('html_url'))
  else:
    url_list.append(best_match.get('mdmurl'))
  if len(results) > 1:
    results.pop(results.index(best_match))
    answer = answer + '<br><br>Aqui tenho outros artigos que podem ajudar:'
    sanitized_answer = sanitized_answer + '\n\n\nAqui tenho outros artigos que podem ajudar:'
    tmp_results = results[:k]
    for r in tmp_results:
      if not elasticsearch:
        title = r['title']
        url = r['html_url']
        url_list.append(url)
      else:
        title = r['mdmtitle']
        url = r['mdmurl']
        url_list.append(url)
      answer = answer + f'<br><b><a target="{target}" rel="noopener noreferrer" href="{url}" style="text-decoration: underline">{title}</a></b><br>'
      sanitized_answer = sanitized_answer + f'\n{title}:\n{url}\n'
  # Caso tenhamos a informação de seção do melhor match nós adicionamos ao final da resposta
  # o link da seção
  if section and section_url:
    answer += f'<br>Caso o artigo que você procura não tenha sido apresentado acima você ainda pode procurá-lo aqui na seção:'
    answer += f'<br><b><a target="{target}" rel="noopener noreferrer" href="{section_url}" style="text-decoration: underline">{section}</a></b><br>'
    sanitized_answer += f'<br>Caso o artigo que você procura não tenha sido apresentado acima você ainda pode procurá-lo aqui na seção:\n{section_url}'
  return answer, sanitized_answer, url_list

def get_answer_page_views(login, channel, elasticsearch, article_results=None):
  # Criamos a resposta para o usuário usando métricas de acesso dos artigos vindas
  # do Google Analytics
  from pycarol.query import Query

  # Caso o canal não seja o portal não podemos abrir uma nova aba no navegador.
  target = '_blank'
  if channel != 'portal':
    target = '_placeholder'

  query = Query(login, sort_order='DESC', sort_by='mdmGoldenFieldAndValues.views')
  # Se o modelo retornou matches da pergunta do usuário com artigos nós usamos as métricas
  # para pegar os artigos mais acessados dentre os artigos que foram selecionados pelo
  # modelo
  if article_results:
    article_results_ids = []
    article_results_ids_tmp = [result.get('id') for result in article_results]
    for id in article_results_ids_tmp:
      if id not in article_results_ids:
        article_results_ids.append(id)
    params = {'ids': article_results_ids}
  # Caso não tenham artigos retornados pelo modelo retornamos os artigos mais consultados
  # para o módulo selecionado
  else:
    params = {'module': module}

  # Fazemos a query na data model das métricas do Analytics na Carol  
  page_views_results = query.named(named_query = 'get_document_views', json_query=params).go().results
  if not page_views_results:
    return None, None, None
  # Pegamos até 5 artigos dos artigos mais consultados
  page_views_results = page_views_results[:5]
  # Se não temos os artigos retornados pelo modelo precisamos pegar as informações
  # dos artigos retornados pela query do Analytics usando seus ids
  if not article_results:
    query = Query(login)
    page_views_ids = [page_view.get('documentid') for page_view in page_views_results]
    params = {'ids': article_results_ids}
    article_results = query.named(named_query = 'get_documents_by_ids', json_query=params).go().results
  best_match = None
  # Iniciamos a montagem da resposta
  answer = 'Sua busca foi abrangente e retornou muitos resultados.'
  answer += f'<br>Aqui estão os {len(page_views_results)} artigos relacionados à sua pergunta que foram mais consultados pelos nossos clientes.'
  # Para cada um dos artigos mais consultados adicionamos seu título com sua respectiva URL de acesso
  url_list = []
  for i, result in enumerate(page_views_results):
    article_id = result.get('documentid')
    document_result = [result for result in article_results if str(result.get('id')) == article_id]
    if document_result:
      document_result = document_result[0]
    else:
      continue
    # Consideramos como o melhor match o artigo mais consultado
    if i == 0:
      best_match = document_result
    if elasticsearch:
      title = document_result.get('mdmtitle')
      url = document_result.get('mdmurl')
      url_list.append(url)
    else:
      title = document_result.get('title')
      url = document_result.get('html_url')
      url_list.append(url)
    answer +=  f'<br><b><a target="{target}" rel="noopener noreferrer" href="{url}" style="text-decoration: underline">{title}</a></b><br>'
  if not best_match:
    return None, None, None
  # Caso tenhamos a informação de seção do melhor match nós adicionamos ao final da resposta
  # o link da seção
  section = best_match.get('section')
  if elasticsearch:
    section_url = best_match.get('sectionurl')
  else:
    section_url = best_match.get('section_html_url')
  if section_url:
    if not section:
      section = 'Clique aqui'      
    answer += f'<br>Caso o artigo que você procura não tenha sido apresentado acima você ainda pode procurá-lo aqui na seção:'
    answer += f'<br><b><a target="{target}" rel="noopener noreferrer" href="{section_url}" style="text-decoration: underline">{section}</a></b><br>'
  return answer, best_match, url_list

def get_model_answer(sentence, product, module, tags, threshold, homolog):
  # Fazemos a consulta na API do modelo
  import requests

  # Adicionamos o produto aos filtros da consulta
  filters = [{'filter_field': 'product', 'filter_value': product}]
  # Caso haja um módulo o adicionamos aos filtros da consulta
  if module:
    filters.append({'filter_field': 'module', 'filter_value': module})
  # Adicionamos os bigrams e tigrams aos filtros da consulta
  #if not homolog:
  #  filters.append({'filter_field': 'tags', 'filter_value': tags})

  # Pegamos até 30 artigos com score maior que o threshold para que possamos
  # fazer eventuais filtros depois
  data = {
    'query': sentence,
    'k': '30',
    'threshold': threshold,
    'filters': filters,
    'response_columns': ['id', 'sentence', 'title', 'section_id', 'html_url', 'solution', 'sanitized_solution', 'tags', 'section_html_url', 'module']
  }
  
  # Enviamos a consulta para o modelo
  #if not homolog:
  #  response = requests.post(url='https://protheusassistant-searchsupportdocs.apps.carol.ai/query',
  #                          json=data, timeout=30)
  #else:
  data['threshold_custom'] = {'tags': 90}
  response = requests.post(url='https://protheusassistant-searchdocshomolog.apps.carol.ai/query',
                          json=data, timeout=30)

  if response.status_code != 200:
    return [], 0

  response = response.json()
        
  if not response:
    return [], 0

  # Retornamos os artigos com maior score e o total de artigos encontramos acima do threshold fornecido
  results = response.get('topk_results')
  total_matches = response.get('total_matches')
    
  return results, total_matches


def get_results(results, channel, segment, elasticsearch=False, k=3, homolog=False):
  # Baseado nos resultados do modelo ou do elasticsearch retornamos a resposta
  # avaliando se é necessário usar as métricas do Analytics
  import re
  analytics = False
  # Mais de 5 artigos retornados na pesquisa retornamos os artigos mais consultados
  # baseados nas métricas do Google Analytics
  if len(results) > 10 and segment == 'Plataformas':
    login = Carol(domain='protheusassistant',
              app_name=' ',
              organization='totvs',
              auth=ApiKeyAuth('12bb49601ef541a4b59ae86d67e5ab02'),
              connector_id='278270a32da04d8f905590937fbb3fef')
    # Obtemos a resposta e o melhor match atráves das métricas do Analytics
    answer, best_match, url_list = get_answer_page_views(login, channel, elasticsearch, article_results=results)
    if not best_match:
      # Pegamos os k top resultados, o padrão é 3.
      results = results[:k]
      # Consideramos o melhor match o primeiro item da lista pois possui
      # mais consultas, de acordo com as métricas.
      best_match = results[0]
    # Coletamos a URL, título e labels do melhor match
    if elasticsearch:
      url_best_match = best_match.get('mdmurl')
      title_best_match = best_match.get('mdmtitle')
      labels = re.sub('\[|\]|\"', '', best_match['labels']).split(',')
    else:
      url_best_match = best_match.get('html_url')
      title_best_match = best_match.get('title')
      labels = best_match.get('tags')
    # Montamos a resposta e resposta limpa baseado nos resultados
    if not answer:
      answer, sanitized_answer, url_list = get_answer(best_match, results, url_best_match, title_best_match, elasticsearch, k)
    else:
      sanitized_answer = answer
  else:
    # Pegamos os k top resultados, o padrão é 3.
    results = results[:k]
    # Consideramos o melhor match o primeiro item da lista pois possui maior score
    best_match = results[0]
    # Coletamos a URL, título e labels do melhor match
    if elasticsearch:
      url_best_match = best_match.get('mdmurl')
      title_best_match = best_match.get('mdmtitle')
      labels = re.sub('\[|\]|\"', '', best_match['labels']).split(',')
    else:
      url_best_match = best_match.get('html_url')
      title_best_match = best_match.get('title')
      labels = best_match.get('tags')
    analytics = True
    # Montamos a resposta e resposta limpa baseado nos resultados
    answer, sanitized_answer, url_list = get_answer(best_match, results, url_best_match, title_best_match, elasticsearch, k)

  return answer, best_match, title_best_match, url_best_match, labels, sanitized_answer, url_list, analytics

def update_user_access(login, product, module, segment, question, email):
  # Salva o produto, módulo, horário atual e e-mail da consulta em um data model.
  from pycarol import Staging
  from datetime import datetime

  now = datetime.now().isoformat()

  record = [{'lastsearchedmodule': module,
  'lastaccess': now,
  'email': email,
  'lastsearchedproduct': product,
  'lastsearchedsegment': segment,
  'lastsearchedquestion': question}]
  Staging(login).send_data(staging_name='user_access',
        connector_id='2fa99cd791a140aa903be33eda3f4108',
        data=record)


def main():

    """
      Globals:
        parameters: list of parameters
        query: last user message
        message: message coming from this node, before this execution
        language: e.g. pt-br, en-us
        slotFilling: if this fulfillment was called to fill a parameter

      Overwritting parameters:
        parameters['size'] = 'large'

      Response examples:
        return textResponse('which size do you prefer?')
        return optionResponse('please, choose a size', ['small', 'medium', 'large'])
    """
    import re
    import operator
    import copy
    import requests
    import json
    import random as random
    from pycarol import Carol, Staging, ApiKeyAuth
    from pycarol.query import Query
    from fuzzywuzzy import fuzz
    from unidecode import unidecode

    # Frases para mapear intenções relacionadas com "falar com analista"
    analista_questions =  [
            'falar com analista',
            'quero falar com um analista',
            'falar com atendente',
            'quero falar com atendente',
            'falar com suporte',
            'quero falar com suporte'
            'atendimento humano',
            'abrir ticket',
            'Como abrir chamado',
            'quero abrir chamado',
            'chamado',
            'abrir chamado a totvs',
            'abrir chamado',
            'abrir chamado modulo faturamento',
            'abrir chamado modulo rh',
            'abrir chamado modulo estoque']
    # Opções de respostas para quando o usuário enviar apenas uma palavra na pergunta.
    respostas_uma_palavra = ['Poderia detalhar um pouco mais sua dúvida?',
             'Me conte com mais detalhes a sua dúvida.',
             'Poderia digitar sua dúvida com mais de uma palavra?',
             'Para que eu possa lhe ajudar, preciso que digite mais de uma palavra']
    # Opções de respostas para quando o usuário falar algo relacionado com "falar com analista"
    resposta_analista = ['Estou aqui para te ajudar. Consulte sobre um produto e digite sua dúvida.',
                     'Se você me contar o que precisa, acho que consigo te ajudar.',
                     'Posso tentar ajudar você. Consulte sobre um produto e digite sua dúvida.']
    
    # Frases para mapear intenções relacionadas com "falar com Administrativo"
    cst_questions =  [
            'falar com administrativo',
            'falar com cst',
            'consultar contrato',
            'consultar boleto',
            'atualizar boleto',
            'administrativo']
    # Opções de respostas para quando o usuário falar algo relacionado com "falar com administrativo"
    resposta_cst = ['Por enquanto eu consigo ajudar com dúvidas sobre o seu produto.',
                     'Para assuntos administrativos consulte o Centro de Serviço da TOTVS.']

    # Frases para mapear intenções relacionadas com "falar com Cloud"
    cloud_questions =  [
            'falar com cloud',
            'cloud',
            'assuntos do cloud',
            'atendimento cloud',
            'protheus cloud']
    # Opções de respostas para quando o usuário falar algo relacionado com "falar com Cloud"
    resposta_cloud = ['Desculpe, eu ainda não consigo te ajudar em assuntos sobre Cloud, mas já estou me preparando.<br>Agora você pode tirar dúvidas relacionadas ao seu produto.']

    # Frases para mapear intenções relacionadas com consulta de tickets
    ticket_questions = ['consultar chamado', 'consultar ticket', 'consultar solicitação']

    # Pegamos dos parâmetros a pergunta do usuário, o módulo e o produto selecionados.
    question = parameters.get('question')
    module = parameters.get('module')
    product = parameters.get('product')
    segment = parameters.get('segment')

    parameters.pop('source', None)

    # Pegamos o canal em que o usuário está acessando, o padrão é o TOTVS News.
    # Outras opções são: portal e icone_protheus.
    channel = parameters.get('channel', 'news')
    module_original = parameters.get('module.original')
    # Coletamos se o usuário é um curador.
    curator_agent = parameters.get('curator_agent')
    test = parameters.get('test')
    homolog = parameters.get('homolog')

    # Lê e-mail do usuário
    email = parameters.get('user_email')
    if not email:
      email = parameters.get('email')

    # Cria os custom logs.
    custom_log = get_custom_log(parameters)
    
    # Cria uma variável temporária que é a versão em minúsculo e sem caracteres especiais da questão do usuário.
    question_tmp = unidecode(question.lower())
    # Valida se o usuário está perguntando algo relacionado a "falar com analista".
    # Em caso positivo respondemos que o assistente pode tentar ajudá-lo primeiro.
    matched_analist_questions = [analist_question for analist_question in analista_questions if fuzz.ratio(question_tmp, analist_question) >= 90]
    if matched_analist_questions:
      return textResponse(random.choice(resposta_analista), jumpTo='Consulta BC', customLog=custom_log)

    matched_cst_questions = [cst_question for cst_question in cst_questions if fuzz.ratio(question_tmp, cst_question) >= 90]
    if matched_cst_questions:
      return textResponse(random.choice(resposta_cst), jumpTo='Consulta BC', customLog=custom_log)

    matched_cloud_questions = [cloud_question for cloud_question in cloud_questions if fuzz.ratio(question_tmp, cloud_question) >= 90]
    if matched_cloud_questions:
      return textResponse(random.choice(resposta_cloud), jumpTo='Consulta BC', customLog=custom_log)

    matched_ticket_questions = [ticket_question for ticket_question in ticket_questions if fuzz.ratio(question_tmp, ticket_question) >= 90]
    if re.search('[0-9]{7,}', question_tmp) or matched_ticket_questions:
      return textResponse('Entendi que você está querendo consultar uma solicitação. Vou te levar para o menu de seleção e você poderá selecionar a opção de "Consultar solicitação".', jumpTo='Identificar assunto')

    # Só enviamos a pergunta do usuário para o modelo caso o módulo e o produto tenham sido informados.  
    if question and module and product:
      # Separa a pergunta do usuário em uma lista de palavras
      word_tokens = question.split()
      # Valida se o usuário enviou menos de uma palavra.
      # Em caso positivo pedimos para que eles usem mais palavras para evitar buscar muito abrangentes.
      if len(word_tokens) < 2:
        return textResponse(random.choice(respostas_uma_palavra), jumpTo='Consulta BC', customLog=custom_log)
      #if question.lower() == 'sim':
      #  return textResponse('Perfeito. Agora preciso que você digite sua dúvida.', jumpTo='Consulta BC', customLog=custom_log)
      #if module.lower() == 'pep 2.0 web':
      # product = 'Soluções Saúde'

      # Fazemos login nesse ambiente da Carol usando o pyCarol
      login = Carol(domain='protheusassistant',
              app_name=' ',
              organization='totvs',
              auth=ApiKeyAuth('12bb49601ef541a4b59ae86d67e5ab02'),
              connector_id='278270a32da04d8f905590937fbb3fef')
      # Criamos uma instancia da classe Query da Carol
      query = Query(login)

      # Atualizamos os dados de acesso do usuário com o produto, módulo e e-mail do usuário.
      if not test:
        update_user_access(login, product, module, segment, question, email)

      # Se o usuário enviar como pergunta exatamente a mesma sentença que ele enviou para informar o módulo
      # nós retornamos os 5 artigos mais consultados daquele módulo baseado nas métricas do Google Analytics.
      if module_original and question.lower() == module_original.lower():
        answer, best_match, url_list = get_answer_page_views(login, channel, elasticsearch=True, article_results=None)
        if answer:
          labels = re.sub('\[|\]|\"', '', best_match['labels']).split(',')
          parameters['labels'] = labels
          parameters['section_id'] = best_match.get('sectionid')
          parameters['title'] = best_match.get('mdmtitle')
          parameters['last_url'] = best_match.get('mdmurl')
          for i, url in enumerate(url_list):
            idx = i + 1
            if url:
              parameters[f'url_{idx}'] = url
          parameters['last_answer'] = answer
          custom_log = get_custom_log(parameters)
          return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

      # TODO: Família de módulos
      related_modules = []
      if segment.lower() == 'plataformas': # and not homolog:
        params = {'module': module, 'segment': segment}
        related_modules = query.named(named_query = 'get_related_modules', json_query=params).go().results
        if related_modules:
          related_modules = related_modules[0].get('relatedmodules').split(',')
          related_modules = [related_module.strip() for related_module in related_modules]
          params = {'modules': related_modules, 'segment': segment}
          related_products = query.named(named_query = 'get_products_by_modules', json_query=params).go().results
          if related_products:
            related_products = list({related_product.get('product').strip() for related_product in related_products})
          else:
            related_products = product
        else:
          related_modules = []

      # Se o módulo for do produto Framework (Linha RM) ou Framework (Linha Datasul) usar
      # todos os módulos do produto na busca.
      if module == 'Framework' or module == 'Framework e Tecnologia':
        module = None

      # Salvamos a pergunta do usuário nos parâmetros para usar esta informações em outro nó.  
      parameters['last_question'] = question
      # Removemos alguns caracteres da pergunta do usuário
      question = re.sub('º|ª|°|˚|-', '', question)
      # Criamos uma variável que contém uma cópia da pergunta do usuário onde removemos as barras
      filtered_sentence = question.replace('/', ' ').replace('"', '')

      # Removemos os caracteres especiais da sentença filtrada
      filtered_sentence = unidecode(filtered_sentence)

      # Criamos bigrams e trigrams a partir da pergunta do usuário para
      # filtrarmos os artigos baseando-nos nas tags
      unigrams = remove_punctuation(filtered_sentence.lower()).split()
      bigrams = get_n_grams(filtered_sentence, N=2)
      trigrams = get_n_grams(filtered_sentence, N=3)
      tags = copy.deepcopy(unigrams)
      tags.extend(bigrams)
      tags.extend(trigrams)
      del unigrams
      del bigrams
      del trigrams

      # Definimos 3 thresholds em ordem decrescente.
      thresholds = [65, 55, 45]
      #if 'rejeicao' in filtered_sentence:
      #  thresholds = [85]
      # Se a pergunta do usuário apenas tiver duas palavras usamos apenas o maior threshold.
      #if len(word_tokens) == 2:
      #  thresholds = [thresholds[-1]]
      
      # Enviamos a pergunta do usuário para o modelo com seus respectivos produto, módulo, bigrams e trigrams
      # Nesta etapa usamos o menor threshold para obter o maior número de matches.
      results, total_matches = get_model_answer(filtered_sentence, product, module, tags, thresholds[-1], homolog)
      
      # Enviamos a pergunta do usuário para o modelo mas agora com os módulos da família do módulo selecionado.
      # Nesta etapa usamos o menor threshold para obter o maior número de matches.
      related_modules_results = []
      if related_modules:
        related_modules_results, related_modules_total_matches = get_model_answer(filtered_sentence, related_products, related_modules, tags, thresholds[-1], homolog)

      # Se o modelo retornou resultados nós ordenamos os artigos em ordem decrescente de acordo com o score.
      if results:
        results = sorted(results, key=operator.itemgetter('score'), reverse=True)
      
      # Se o modelo retornou resultados para a família de módulos nós ordenamos os artigos em ordem decrescente de acordo com o score.
      if related_modules_results:
        related_modules_results = sorted(related_modules_results, key=operator.itemgetter('score'), reverse=True)

      # Iteramos a lista de threshold, de forma a irmos diminuindo o threshold
      # até obtermos uma resposta
      for threshold in thresholds:
        best_match = None
        tmp_results = [result for result in results if result.get('score') >= threshold/100]
        tmp_related_modules_results = [result for result in related_modules_results if result.get('score') >= threshold/100]
        # Obtemos a resposta, o melhor match e suas respectivas informações
        if tmp_results:
          answer, best_match, title_best_match, url_best_match, labels, sanitized_answer, url_list, analytics = get_results(tmp_results, channel, segment, elasticsearch=False, k=3, homolog=homolog)
        elif tmp_related_modules_results:
          answer, best_match, title_best_match, url_best_match, labels, sanitized_answer, url_list, analytics = get_results(tmp_related_modules_results, channel, segment, elasticsearch=False, k=3, homolog=homolog)
        # Caso o melhor match tenha sido encontrado para o atual threshold salvamos
        # suas informações nos parâmetros para usarmos na abertura do ticket.
        if best_match:
          parameters['labels'] = labels
          parameters['section_id'] = best_match.get('section_id')
          parameters['title'] = title_best_match
          parameters['last_url'] = url_best_match
          for i, url in enumerate(url_list):
            idx = i + 1
            if url:
              parameters[f'url_{idx}'] = url
          parameters['last_answer'] = sanitized_answer
          parameters['module'] = best_match.get('module')
          # Criamos um novo log customizado com os parâmetros atualizados
          parameters['source'] = 'modelo'
          parameters['analytics'] = analytics
          custom_log = get_custom_log(parameters)
          # Retornamos a resposta para o usuário
          return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

      # Fallback: Elasticsearch
      best_match = None
      filtered_sentence = filtered_sentence.replace('\"', '')
      params = {'text': filtered_sentence, 'module': [module], 'product': product}
      query = Query(login, get_aggs=True, only_hits=False)
      response = query.named(named_query = 'get_document_that_contains', json_query=params).go().results
      if response and response[0].get('hits'):
        results = sorted(response[0].get('hits'), key=operator.itemgetter('_score'), reverse=True)
      elif related_modules:
        params = {'text': filtered_sentence, 'module': related_modules, 'product': product}
        response = query.named(named_query = 'get_document_that_contains', json_query=params).go().results
        if response and response[0].get('hits'):
          results = sorted(response[0].get('hits'), key=operator.itemgetter('_score'), reverse=True)
      if results:
        results = [result.get('mdmGoldenFieldAndValues') for result in results if result.get('_score') > 18]
        aux = []
        for r in results:
          if r.get('id') not in [b.get('id') for b in aux]:
            aux.append(r)
        results = aux
        answer, best_match, title_best_match, url_best_match, labels, sanitized_answer, url_list, analytics = get_results(results, channel, segment, elasticsearch=True, k=3, homolog=homolog)
      if best_match:
        parameters['labels'] = labels
        parameters['section_id'] = best_match.get('section_id')
        parameters['title'] = title_best_match
        parameters['last_url'] = url_best_match
        for i, url in enumerate(url_list):
          idx = i + 1
          if url:
            parameters[f'url_{idx}'] = url
        parameters['last_answer'] = sanitized_answer
        parameters['module'] = best_match.get('module')
        parameters['source'] = 'elasticsearch'
        parameters['analytics'] = analytics
        custom_log = get_custom_log(parameters)
        return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

      # Caso nenhum artigo tenha sido retornado pela busca do usuário nós damos mais 2 tentativas
      # para eles tentarem refazer a consulta usando outras palavras antes de enviá-los para o fluxo
      # de transbordo ou abertura de ticket.

      # Lê a quantidade de tentativas que o usuário já fez. Caso seja a primeira tentativa o valor padrão é 0.
      attempts = parameters.get('attempts', 0)
      body = copy.deepcopy(parameters.get('body', 'Últimas perguntas:'))
      answer = 'Desculpe, eu ainda não sei responder esta pergunta.'
      # Adicionamos uma tentativa às tentativas do usuário
      attempts = int(attempts) + 1
      body += f'\n{attempts}ª Pergunta: {question}\n'
      # Salvamos o corpo do ticket, o número de tentativas e se o usuário atingiu o máximo de tentativas
      # nos parâmetros para que possamos coletar essas informações na próxima tentativa.
      parameters['body'] = body
      parameters['attempts'] = attempts
      parameters['max_attempts'] = False
      # Caso ainda não tenham sido feitas 3 tentativas pedimos para os usuários
      # tentarem refazer a consulta usando outras palavras
      if attempts < 3:
        answer += ' Você poderia digitar sua dúvida com outras palavras?'
        jump_to = 'Consulta BC'
      # Caso as 3 tentativas já tenham sido feitas levamos os usuários para o fluxo
      # de transbordo ou abertura de ticket
      else:
        # Como nenhum artigo foi encontrado definimos automaticamente o feedback como negativo
        parameters['custom_feedback'] = 'no'
        # Analisamos se o usuário é um curador que pode abrir tickets
        curator_agent_ticket = parameters.get('curator_agent_ticket', False)
        # Caso o usuário seja um curador e não possa abrir ticket os guiamos para o nó de feedback negativo
        # e removemos o corpo do ticket (body) dos parâmetros
        if curator_agent and not curator_agent_ticket:
          jump_to = 'Feedback negativo'
          parameters.pop('body', None)
        # Caso o usuário não seja um curador ou seja um curador que pode abrir tickets
        # nós os guiamos para o nó de abertura de ticket de log
        else:
          jump_to =  'Criar ticket de log'
          # Guardamos a última resposta dada pelo assistente nos parâmetros
          # para usarmos essa informação na abertura do ticket
          parameters['last_answer'] = answer
          # Identificamos nos parâmetros que o usuário usou o máximo de tentativas
          parameters['max_attempts'] = True
        # Como nenhum artigo foi encontrado removemos quaisquer URLs, seções e labels
        # que pudessem estar salvas nos parâmetros
        parameters.pop('last_url', None)
        for i in range(1, 6):
          parameters.pop(f'url_{i}', None)
        parameters.pop('section_id', None)
        parameters.pop('labels', None)
      # Criamos um novo log customizado com os parâmetros atualizados
      custom_log = get_custom_log(parameters)
      # Retornamos a resposta para o usuário o guiando para o devido nó
      return textResponse(answer, jumpTo=jump_to, customLog=custom_log)

    # Caso o usuário não tenha fornecido um e-mail, produto ou módulo
    # não podemos fazer a consulta e portanto precisamos pedir por estas
    # informações
    complementary_message = ''
    # Se o e-mail não ter sido fornecido ou a sessão tenha expirado
    # guiamos o usuário para o nó de autenticação
    if channel != 'portal' and not email:
      jump_to = 'Autenticação do Cliente'
      complementary_message = ' Mas antes precisamos te autenticar novamente.'
    # Caso contrário o guiamos para o nó de identificar assunto onde
    # caso eles queiram fazer perguntas sobre o produto deverão fornecer
    # o nome do módulo
    else:
      jump_to = 'Identificar assunto'
        
    return textResponse(f'Tudo bem, voltando ao início.{complementary_message}', jumpTo=jump_to, customLog=custom_log)