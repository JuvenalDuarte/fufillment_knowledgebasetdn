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


def get_answer(best_match, results, field_mapping, k=3, pageviews=False):
    import json

    # Pega o conteúdo dos atributos esperados, dependo da fonte, através do
    # dicionário de mappings
    d = field_mapping
    target = '_blank'

    # Tratando resultado principal: best match, maior score
    if not pageviews:

        # Os atributos usados dependem da fonte do artigo. Primeiro recuperamos esta fonte pelo atributo 
        # 'source' no artigo, em seguinda a usamos no dicionário field_mapping para localizar o nome da
        # coluna correspondente em cada uma das fontes
        header = best_match.get(d[best_match.get('source')]["header"])
        header_ref = best_match.get(d[best_match.get('source')]["header_ref"])
        content = best_match.get(d[best_match.get('source')]["content"])
        content = resize_images(content)
        content = resize_videos(content)
        sancontent = best_match.get(d[best_match.get('source')]["sanitized_content"])
        labels = best_match.get(d[best_match.get('source')]["tags"])

        # Adicionamos ao início da resposta o título do artigo de melhor match com sua respectiva URL de acesso
        answer = f'<br><b><a target="{target}" rel="noopener noreferrer" href="{header_ref}" style="text-decoration: underline"><strong>{header}</strong></a></b><br>' + content
        
        # Caso o artigo com maior score seja do TDN adicionamos o link para o patch, caso disponível
        if best_match.get('source') == "tdn":

            # Caso o atributo esteja preenchido
            if best_match.get('patch_url'):
                patch = best_match.get('patch_url')
                patches_d = json.loads(patch)
                patch_links = []

                # Adicionamos o link para cada uma das versões disponíveis.
                for kv in patches_d.keys():
                    v = "Todas" if (kv == "None" or kv == "null" or kv is None) else kv
                    patch_links.append(f'<a target="{target}" rel="noopener noreferrer" href="{patches_d[kv]}" style="text-decoration: underline">{v}</a>')

                answer += f'<br>Selecione a versão para baixar pacote de atualização:' + ", ".join(patch_links)
        
        sanitized_answer = sancontent + f'\n\nURL: {header_ref}'
    else:
        header = header_ref = labels = None

    # Artigos secundários: Os demais artigo são exibidos de maneira resumida, só título e url, sem detalhes.
    url_list = []
    if len(results) > 1:
        if not pageviews:
            results.pop(results.index(best_match))
            answer = answer + '<br><br>Aqui tenho outros artigos que podem ajudar:'
            sanitized_answer = sanitized_answer + '\n\n\nAqui tenho outros artigos que podem ajudar:'

        else:
            answer = f'Sua busca foi abrangente e retornou muitos resultados. Aqui estão os {len(results)} artigos relacionados à sua pergunta que foram mais consultados pelos nossos clientes.'
            sanitized_answer = answer

        tmp_results = results[:k]

        for r in tmp_results:
            detail_header = r.get(d[r.get('source')]["header"])
            detail_header_ref = r.get(d[r.get('source')]["header_ref"])
            url_list.append(detail_header_ref)

            answer = answer + f'<br><b><a target="{target}" rel="noopener noreferrer" href="{detail_header_ref}" style="text-decoration: underline">{detail_header}</a></b><br>'
            sanitized_answer = sanitized_answer + f'\n{detail_header}:\n{detail_header_ref}\n'

    #return "get_results.get_answer.checkpoint=2", "", [], "", "", []

    # Caso tenhamos a informação de seção do melhor match nós adicionamos ao final da resposta
    # o link da seção
    if d[best_match.get('source')]["section_url"] in best_match:

        section_url = best_match.get(d[best_match.get('source')]["section_url"])

        if d[best_match.get('source')]["section"] in best_match:
            section = best_match.get('section')
        else:
            section = 'Clique aqui'

        answer += f'<br>Caso o artigo que você procura não tenha sido apresentado acima você ainda pode procurá-lo aqui na seção:'
        answer += f'<br><b><a target="{target}" rel="noopener noreferrer" href="{section_url}" style="text-decoration: underline">{section}</a></b><br>'
        sanitized_answer += f'<br>Caso o artigo que você procura não tenha sido apresentado acima você ainda pode procurá-lo aqui na seção:\n{section_url}'

    return answer, sanitized_answer, url_list, header, header_ref, labels

def orderby_page_views(login, article_results, k=5):
    # Criamos a resposta para o usuário usando métricas de acesso dos artigos vindas
    # do Google Analytics
    from pycarol.query import Query

    # identificando todos os ids unicos e adicionando-os como filtros da busca
    uniq_ids = list(set([result.get('id') for result in article_results]))
    params = {'ids': uniq_ids}

    # Fazemos a query na data model das métricas do Analytics na Carol  
    query = Query(login, sort_order='DESC', sort_by='mdmGoldenFieldAndValues.views')
    page_views_results = query.named(named_query = 'get_document_views', json_query=params).go().results

    # itera os conteudos com mais visualizações
    article_results_ranked = []
    for i, pageview in enumerate(page_views_results):        
        document_result = [result for result in article_results if str(result.get('id')) == pageview.get('documentid')]
        document_result = document_result[0]
        document_result.update({"source":"kcs"})
        article_results_ranked.append(document_result)

    if article_results_ranked:
        # Pegamos até 5 artigos dos artigos mais consultados
        article_results_ranked = article_results_ranked[:k]
    else:
        article_results_ranked = article_results

    return article_results_ranked


def top_page_views(login, module, k):
    # Criamos a resposta para o usuário usando métricas de acesso dos artigos vindas
    # do Google Analytics
    from pycarol.query import Query

    query = Query(login)
    params = {'module': module}
    page_views_results = query.named(named_query = 'get_document_views', json_query=params).go().results

    page_views_ids = [page_view.get('documentid') for page_view in page_views_results]
    params = {'ids': page_views_ids}
    article_results = query.named(named_query = 'get_documents_by_ids', json_query=params).go().results

   # itera os conteudos com mais visualizações
    article_results_ranked = []
    for i, pageview in enumerate(page_views_results):        
        document_result = [result for result in article_results if str(result.get('id')) == pageview.get('documentid')]
        article_results_ranked.append(document_result)

    if article_results_ranked:
        # Pegamos até 5 artigos dos artigos mais consultados
        article_results_ranked = article_results_ranked[:k]
        best_match = article_results_ranked[0]
    else:
        article_results_ranked = best_match = None

    return best_match, article_results_ranked


def get_model_answer(sentence, product, module, tags, threshold, db="KCS"):
    # Fazemos a consulta na API do modelo
    import requests

    # Pegamos até 30 artigos com score maior que o threshold para que possamos
    # fazer eventuais filtros depois
    data = {
        'query': sentence,
        'threshold': threshold
    }

    # Define os filtros e os atributos dependendo da base 
    if db == "KCS":
        # Adicionamos o produto aos filtros da consulta
        filters = [{'filter_field': 'product', 'filter_value': product}]
        # Caso haja um módulo o adicionamos aos filtros da consulta
        if module:
            filters.append({'filter_field': 'module', 'filter_value': module})
        # Adicionamos os bigrams e tigrams aos filtros da consulta
        filters.append({'filter_field': 'tags', 'filter_value': tags})

        data['k'] = 30
        data['filters'] = filters
        data['response_columns'] = ['id', 'sentence', 'title', 'section_id', 'html_url', 'solution', 'sanitized_solution', 'tags', 'section_html_url', 'module']
        api_url = 'https://protheusassistant-searchsupportdocs.apps.carol.ai/query'

    elif db == "TDN":
        if module:
            filters = [{'filter_field': 'modulo', 'filter_value': module}]

        data['k'] = 10
        data['filters'] = filters
        data['response_columns'] = ['id', 'html_url', 'solucao', "patch_version", "patch_url", "summary", "situacao_requisicao"]
        api_url = 'https://sentencesimilarity-tdnknowledgebase.apps.carol.ai/query'
       
    # Enviamos a consulta para o modelo
    response = requests.post(url=api_url, json=data)

    if response.status_code != 200:
        return [], 0

    response = response.json()
        
    if not response:
        return [], 0

    # Retornamos os artigos com maior score e o total de artigos encontramos acima do threshold fornecido
    results = response.get('topk_results')
    total_matches = response.get('total_matches')

    return results, total_matches


def get_results(login, results, k=3):
    # Baseado nos resultados do modelo ou do elasticsearch retornamos a resposta
    # avaliando se é necessário usar as métricas do Analytics
    import re

    # Caso houverem muitos resultados para uma busca KCS, seleciona os artigos mais vistos
    # ATENÇÂO: Quando temos muitos artigos os documentos TDN são descartados, pois ainda não temos
    # page views para estes artigos.
    pv=False
    if (len(results) > 10):
        results = orderby_page_views(login, article_results=results)
        pv=True

    # Consideramos o melhor match o primeiro item da lista pois possui maior score
    best_match = results[0]

    # Pegamos os k top resultados, o padrão é 3.
    results = results[:k]

    field_mapping = {"kcs" : {"header": "title",
                              "header_ref": "html_url",
                              "content": "solution",
                              "sanitized_content":"sanitized_solution",
                              "tags": "tags",
                              "section":"section",
                              "section_url":"section_html_url"},

                     "elasticsearch" : {"header": "mdmtitle",
                              "header_ref": "mdmurl",
                              "content": "solution",
                              "sanitized_content":"sanitizedsolution",
                              "tags": "labels",
                              "section":"section",
                              "section_url":"sectionurl"},
                     
                     "tdn" : {"header": "summary",
                              "header_ref": "html_url",
                              "content": "situacao_requisicao",
                              "sanitized_content": "situacao_requisicao",
                              "tags": "labels",
                              "section":"",
                              "section_url":""}}

    #return "get_results.checkpoint=3", "", None, {}

    # Montamos a resposta e resposta limpa baseado nos resultados
    answer, sanitized_answer, url_list, title_best_match, url_best_match, labels = get_answer(best_match, results, field_mapping=field_mapping, k=k, pageviews=pv)

    #return answer, sanitized_answer, best_match, {}

    # Guardando os parâmetros para debug
    parameters = {}
    parameters['labels'] = labels
    parameters['section_id'] = best_match.get('section_id')
    parameters['title'] = title_best_match
    parameters['last_url'] = url_best_match
    parameters['last_answer'] = sanitized_answer
    parameters['module'] = best_match.get('module')
    parameters['source'] = best_match.get('source')

    for i, url in enumerate(url_list):
        if url:
            parameters[f'url_{i+1}'] = url

    return answer, sanitized_answer, best_match, parameters


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
    import random as random
    from pycarol import Carol, Staging, ApiKeyAuth
    from pycarol.query import Query
    from fuzzywuzzy import fuzz
    from unidecode import unidecode

    # Frases para mapear intenções relacionadas com "falar com analista"
    analista_questions =  [
            'falar com analista',
            'falar com atendente',
            'falar com suporte',
            'atendimento humano',
            'abrir ticket',
            'Como abrir chamado',
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
      update_user_access(login, product, module, segment, question, email)

      # Se o usuário enviar como pergunta exatamente a mesma sentença que ele enviou para informar o módulo
      # nós retornamos os 5 artigos mais consultados daquele módulo baseado nas métricas do Google Analytics.
      if module_original and question.lower() == module_original.lower():
        best_match, pv_results = top_page_views(login, module_original, k)
        for item in pv_results: item.update({"source":"elasticsearch"})

        # Obtemos a resposta, o melhor match e suas respectivas informações
        answer, san_answer, best_match, parms = get_results(login, pv_results, k=3)
        parameters.update(parms)
        custom_log = get_custom_log(parameters)

        return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

      # TODO: Família de módulos
      related_modules = []
      if curator_agent:
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
      if module == 'Framework':
        module = None

      # Salvamos a pergunta do usuário nos parâmetros para usar esta informações em outro nó.  
      parameters['last_question'] = question
      # Removemos alguns caracteres da pergunta do usuário
      question = re.sub('º|ª|°|˚|-', '', question)
      # Criamos uma variável que contém uma cópia da pergunta do usuário onde removemos as barras
      filtered_sentence = question.replace('/', ' ')

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
      if 'rejeicao' in filtered_sentence:
        thresholds = [85]
      # Se a pergunta do usuário apenas tiver duas palavras usamos apenas o maior threshold.
      #if len(word_tokens) == 2:
      #  thresholds = [thresholds[-1]]

      # Enviamos a pergunta do usuário para o modelo com seus respectivos produto, módulo, bigrams e trigrams
      # Nesta etapa usamos o menor threshold para obter o maior número de matches.
      results_kcs, total_matches_kcs = get_model_answer(filtered_sentence, product, module, tags, thresholds[-1], db="KCS")
      results_tdn, total_matches_tdn = get_model_answer(filtered_sentence, product, module, tags, thresholds[-1], db="TDN")

      # Enviamos a pergunta do usuário para o modelo mas agora com os módulos da família do módulo selecionado.
      # Nesta etapa usamos o menor threshold para obter o maior número de matches.
      related_modules_results = []
      if related_modules:
        related_modules_results, related_modules_total_matches = get_model_answer(filtered_sentence, related_products, related_modules, tags, thresholds[-1], db="KCS")
      
      # Iteramos a lista de threshold, de forma a irmos diminuindo o threshold
      # até obtermos uma resposta
      answer = ""
      for threshold in thresholds:
        best_match = None

        answer += f"Encontrado um total de {len(results_kcs)} artigos no KCS, {len(results_tdn)} no TDN.\n"

        # Filtrando apenas resultados acima do threshold
        tmp_results_kcs = [result for result in results_kcs if result.get('score') >= threshold/100]
        tmp_results_tdn = [result for result in results_tdn if result.get('score') >= threshold/100]

        answer += f"Artigos acima do threshold {threshold}: {len(tmp_results_kcs)} KCS; {len(tmp_results_tdn)} TDN.\n"

        # ordena o ranking de resultados para cada base e adiciona a tag da origim para facilitar formatação
        for item in tmp_results_kcs: item.update({"source":"kcs"})
        for item in tmp_results_tdn: item.update({"source":"tdn"})

        # Se nenhum artigo for retornado do KCS procura nos módulos relacionados
        if not tmp_results_kcs:
            tmp_results_kcs = [result for result in related_modules_results if result.get('score') >= threshold/100]
            for item in tmp_results_kcs: item.update({"source":"kcs"})
            answer += f"{len(tmp_results_kcs)} adicionados pela pesquisa em módulos relacionados.\n"

        # Coloca todos os artigos acima do threshold em uma mesma lista
        all_results = tmp_results_kcs + tmp_results_tdn

        # Caso nenhum artigo atenda o threshold de score
        if not all_results: continue

        # Ordena a lista pela score
        all_results.sort(key=lambda x: x.get('score'), reverse=True)

        answer += f"Total de {len(all_results)} artigos resultantes.\n"
        #return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

        # Obtemos a resposta, o melhor match e suas respectivas informações
        answer, san_answer, best_match, parms = get_results(login, all_results, k=3)

        parameters.update(parms)
        custom_log = get_custom_log(parameters)
        
        # Retornamos a resposta para o usuário
        return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

      answer += f"Nenhum threshold satisfeito, redirecionando para elastic search.\n"

      # Caso nenhuma resposta satisfaça os thresholds.Fallback: Elasticsearch
      best_match = None
      params = {'text': filtered_sentence, 'module': [module], 'product': product}
      query = Query(login, get_aggs=True, only_hits=False)
      response = query.named(named_query = 'get_document_that_contains', json_query=params).go().results

      answer += f"elasticsearch.checkpoint=1.\n"

      results = []
      if response and response[0].get('hits'):
        results = sorted(response[0].get('hits'), key=operator.itemgetter('_score'), reverse=True)
      elif related_modules:
        params = {'text': filtered_sentence, 'module': related_modules, 'product': product}
        response = query.named(named_query = 'get_document_that_contains', json_query=params).go().results
        if response and response[0].get('hits'):
          results = sorted(response[0].get('hits'), key=operator.itemgetter('_score'), reverse=True)

      answer += f"elasticsearch.checkpoint=2. len(results) = {len(results)}. \n"
      
      if results:
        results = [result.get('mdmGoldenFieldAndValues') for result in results if result.get('_score') > 18]
        aux = []
        for r in results:
          if r.get('id') not in [b.get('id') for b in aux]:
            r["source"] = "elasticsearch"
            aux.append(r)

        results = aux
        answer, san_answer, best_match, parms = get_results(login, results, k=3)

      if best_match:
        parameters.update(parms)
        custom_log = get_custom_log(parameters)
        return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

      answer += f"elasticsearch.checkpoint=4.\n"
    
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

      answer += f"Redirecionando para nova tentativa. attempts={attempts}. \n"

      # Caso ainda não tenham sido feitas 3 tentativas pedimos para os usuários
      # tentarem refazer a consulta usando outras palavras
      if attempts < 3:
        answer += ' Você poderia digitar sua dúvida com outras palavras?'
        jump_to = 'Consulta BC'
      # Caso as 3 tentativas já tenham sido feitas levamos os usuários para o fluxo
      # de transbordo ou abertura de ticket
      else:
        answer += f"Tentativas excedidas: attempts={attempts}. Redirencionando ao fluxo de abertura de ticket.\n"
        #return textResponse(f'{answer}', jumpTo='Criar ticket de log', customLog=custom_log)

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