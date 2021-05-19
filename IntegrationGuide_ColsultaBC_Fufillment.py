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

def get_n_grams(sentence, N=2):
    # Função que cria n grams de uma sentença.
    # Os n grams são criados em minúsculo e sem caracteres especiais.
    # O default são bigrams (N=2): combinações de duas palavras.
    # Os ngrams são juntados por espaço e underline para podermos dar match
    # com as tags do artigos.
    from unidecode import unidecode
    sentence = sentence.lower()
    sentence = sentence.split()
    n_grams_arr = [sentence[i:i+N] for i in range(len(sentence)-N+1)]
    n_grams = [unidecode(' '.join(n_gram)) for n_gram in n_grams_arr]
    n_grams.extend([unidecode('_'.join(n_gram)) for n_gram in n_grams_arr])
    return n_grams
    

def get_answer(best_match, results, url_best_match, title_best_match, elasticsearch=False, k=3):
    import json

    # Coletamos a solução do melhor match
    problem = best_match.get('situacao_requisicao')
    title_best_match = best_match.get('summary')
    url_best_match = best_match.get('html_url')
    patch = best_match.get('patch_url')
    patches_d = json.loads(patch)
    target = '_blank'
    
    answer = f'<br><b><a target="{target}" rel="noopener noreferrer" href="{url_best_match}" style="text-decoration: underline"><strong>{title_best_match}</strong></a></b><br> {problem}' 
    answer += f'<br>Selecione a versão para baixar pacote de atualização:'
    
    versions = 1
    for kv in patches_d.keys():
    
        if kv == "None" or kv == "null" or kv is None:
            v = "Todas"
        else:
            v = kv
            
        if versions == 1:
            answer += f'<a target="{target}" rel="noopener noreferrer" href="{patches_d[kv]}" style="text-decoration: underline">{v}</a>'
        else:
            answer += f', <a target="{target}" rel="noopener noreferrer" href="{patches_d[kv]}" style="text-decoration: underline">{v}</a>' 
            
        versions +=  1

    sanitized_answer = title_best_match + f'\n\nURL: {url_best_match}'

    # Se houverem mais artigos nos resultados criamos a seção Saiba mais com o título de cada artigo
    # e suas respectivas URLs de acesso
    if len(results) > 1:
        results.pop(results.index(best_match))
        answer = answer + '<br><br>Aqui tenho outros artigos que podem ajudar:'
        sanitized_answer = sanitized_answer + '\n\n\nAqui tenho outros artigos que podem ajudar:'

        for r in results[:k]:
            title = r['summary']
            url = r['html_url']

            answer = answer + f'<br><a target="{target}" rel="noopener noreferrer" href="{url}" style="text-decoration: underline">{title}</a><br>'
            sanitized_answer = sanitized_answer + f'\n{title}:\n{url}\n'

    return answer, sanitized_answer


def get_model_answer(sentence, product, module, tags, threshold):
    # Fazemos a consulta na API do modelo
    import requests

    # Adicionamos o produto aos filtros da consulta
    #filters = [{'filter_field': 'produto', 'filter_value': product}]

    # Caso haja um módulo o adicionamos aos filtros da consulta
    if module:
         filters = [{'filter_field': 'modulo', 'filter_value': module}]
    #    filters.append({'filter_field': 'modulo', 'filter_value': module})
    
    # Adicionamos os bigrams e tigrams aos filtros da consulta
    #filters.append({'filter_field': 'tags', 'filter_value': tags})

    # Pegamos até 30 artigos com score maior que o threshold para que possamos
    # fazer eventuais filtros depois
    data = {
        'query': sentence,
        'k': '10',
        'threshold': threshold,
        'filters': filters,
        #'response_columns': ['id', 'sentence', 'title', 'section_id', 'html_url', 'solution', 'sanitized_solution', 'tags', 'section_html_url', 'module']
        'response_columns': ['id', 'html_url', 'solucao', "patch_version", "patch_url", "summary", "situacao_requisicao"]
    }
    
    # Enviamos a consulta para o modelo
    response = requests.post(url='https://sentencesimilarity-tdnknowledgebase.apps.carol.ai/query',
                             json=data)

    if response.status_code != 200:
        return [], 0

    response = response.json()
        
    if not response:
        return [], 0

    # Retornamos os artigos com maior score e o total de artigos encontramos acima do threshold fornecido
    results = response.get('topk_results')
    total_matches = response.get('total_matches')
    
    return results, total_matches


def get_results(results, channel, elasticsearch=False, k=3):
    # Baseado nos resultados do modelo ou do elasticsearch retornamos a resposta
    # avaliando se é necessário usar as métricas do Analytics
    import re

    # Pegamos os k top resultados, o padrão é 3.
    results = results[:k]
    # Consideramos o melhor match o primeiro item da lista pois possui maior score
    best_match = results[0]
    # Coletamos a URL, título e labels do melhor match
    url_best_match = best_match.get('html_url')
    title_best_match = best_match.get('summary')
    labels = best_match.get('solucao')

    # Montamos a resposta e resposta limpa baseado nos resultados
    answer, sanitized_answer = get_answer(best_match, results, url_best_match, title_best_match, elasticsearch, k)

    return answer, best_match, title_best_match, url_best_match, labels, sanitized_answer

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
            'falar com atendente',
            'falar com suporte',
            'atendimento humano',
            'abrir ticket',
            'Como abrir chamado',
            'chamado',
            'abrir chamado a totvs',
            'abrir chamado']
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
            'atendimento cloud']
    # Opções de respostas para quando o usuário falar algo relacionado com "falar com Cloud"
    resposta_cloud = ['Desculpe, eu ainda não consigo te ajudar em assuntos sobre Cloud, mas já estou me preparando.<br>Agora você pode tirar dúvidas relacionadas ao seu produto.']

    # Pegamos dos parâmetros a pergunta do usuário, o módulo e o produto selecionados.
    question = parameters.get('question')
    module = parameters.get('module')
    product = parameters.get('product')

    # Pegamos o canal em que o usuário está acessando, o padrão é o TOTVS News.
    # Outras opções são: portal e icone_protheus.
    channel = parameters.get('channel', 'news')
    module_original = parameters.get('module.original')
    # Coletamos se o usuário é um curador.
    curator_agent = parameters.get('curator_agent')

    # Cria os custom logs.
    custom_log = get_custom_log(parameters)
    complementary_message = ''
    jump_to = 'Modulo'
    
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

    # Só enviamos a pergunta do usuário para o modelo caso o módulo e o produto tenham sido informados.  
    if question and module and product:
        # Separa a pergunta do usuário em uma lista de palavras
        word_tokens = question.split()
        # Valida se o usuário enviou menos de uma palavra.
        # Em caso positivo pedimos para que eles usem mais palavras para evitar buscar muito abrangentes.
        if len(word_tokens) < 2:
            return textResponse(random.choice(respostas_uma_palavra), jumpTo='Consulta BC', customLog=custom_log)

        # TODO: Família de módulos
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
        unigrams = filtered_sentence.lower().split()
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
        #thresholds = [40]
        # Se a pergunta do usuário apenas tiver duas palavras usamos apenas o maior threshold.
        #if len(word_tokens) == 2:
        #  thresholds = [thresholds[-1]]

        # Enviamos a pergunta do usuário para o modelo com seus respectivos produto, módulo, bigrams e trigrams
        # Nesta etapa usamos o menor threshold para obter o maior número de matches.
        results, total_matches = get_model_answer(filtered_sentence, product, module, tags, thresholds[-1])

        # Enviamos a pergunta do usuário para o modelo mas agora com os módulos da família do módulo selecionado.
        # Nesta etapa usamos o menor threshold para obter o maior número de matches.
        related_modules_results = []
        if related_modules:
            related_modules_results, related_modules_total_matches = get_model_answer(filtered_sentence, product, related_modules, tags, thresholds[-1])

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
                answer, best_match, title_best_match, url_best_match, labels, sanitized_answer = get_results(tmp_results, channel, k=3)
            elif tmp_related_modules_results:
                answer, best_match, title_best_match, url_best_match, labels, sanitized_answer = get_results(tmp_related_modules_results, channel, k=3)
                
            # Caso o melhor match tenha sido encontrado para o atual threshold salvamos
            # suas informações nos parâmetros para usarmos na abertura do ticket.
            if best_match:
                parameters['labels'] = labels
                parameters['section_id'] = best_match.get('section_id')
                parameters['title'] = title_best_match
                parameters['last_url'] = url_best_match
                parameters['last_answer'] = sanitized_answer
                parameters['module'] = best_match.get('module')
                # Criamos um novo log customizado com os parâmetros atualizados
                custom_log = get_custom_log(parameters)
                # Retornamos a resposta para o usuário
                return textResponse(f'{answer}', jumpTo='Continuar no módulo', customLog=custom_log)
    
        answer = f"Não encontrei nenhum artigo para \"{filtered_sentence}\" no modulo \"{module}\"."

        return textResponse(answer, jumpTo='Continuar no módulo', customLog=custom_log)
        
    return textResponse(f'Tudo bem, voltando ao início.{complementary_message}', jumpTo=jump_to, customLog=custom_log)