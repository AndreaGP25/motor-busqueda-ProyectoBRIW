from flask import Flask, render_template, request, jsonify
from nltk.corpus import wordnet as wn
import requests

app = Flask(__name__)

SOLR_URL = "http://localhost:8983/solr/mi_core_es"

def search_solr(query, start=0, rows=10, fq=None):
    """Busca en Solr y devuelve resultados"""
    """Busca en Solr con relevancia ponderada usando edismax"""
    """Busca en Solr con faceting"""
    """Busca en Solr con relevancia ponderada"""
    
    params = {
        'q': query,
        'defType': 'edismax',           # ACTIVAR edismax
        'qf': 'titulo^3.0 contenido_es^1.0',  # Título 3x más importante
        'pf': 'titulo^5.0',             # Boost adicional para frases en título
        'tie': '0.1',                   # Balance entre campos
        
        'start': start,
        'rows': rows,  

        'fl': '*,score',  # Solicitar el campo score      

        # Highlight 
        'hl': 'true',
        'hl.fl': 'contenido_es',
        'hl.snippets': 3,
        'hl.fragsize': 200,

         # Facetas
        'facet': 'true',
        'facet.field': ['dominio_facet', 'anio', 'tipo_contenido'],
        'facet.limit': 20,

        # Spellcheck (existente)
        'spellcheck': 'true',
        'spellcheck.q': query,
        'spellcheck.dictionary': 'default',
        'spellcheck.count': 5,
        'spellcheck.collate': 'true',

        'wt': 'json'
    }

    if fq:
        params['fq'] = fq
    
    try:
        response = requests.get(f"{SOLR_URL}/select", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error buscando en Solr: {e}")
        return None


def expand_query_with_wordnet(query):
    palabras = query.split()
    sinonimos_totales = []

    for palabra in palabras:
        syns = wn.synsets(palabra, lang="spa")
        sinonimos = set()

        for s in syns:
            for lemma in s.lemmas(lang="spa"):
                sin = lemma.name().replace("_", " ")
                if sin.lower() != palabra.lower():
                    sinonimos.add(sin)

        if sinonimos:
            grupo = f"({palabra} OR " + " OR ".join(sinonimos) + ")"
            sinonimos_totales.append(grupo)
        else:
            sinonimos_totales.append(palabra)

    return " AND ".join(sinonimos_totales)


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if not query:
        return render_template('index.html', error="Ingresa un término de búsqueda")
    
    page = int(request.args.get('page', 1))
    start = (page - 1) * 10
    

    # Saber si el usuario quiere sinónimos
    usar_semantica = request.args.get("semantica") == "on"
    if usar_semantica:
        query_expanded = expand_query_with_wordnet(query)
    else:
        query_expanded = query
    
    
    fq = request.args.get('fq')   

    # Buscar en Solr
    results = search_solr(query_expanded, start=start, rows=10, fq=fq)

    # Obtener sugerencias de corrección
    spellcheck = results.get("spellcheck", {})
    suggestion = None

    if "suggestions" in spellcheck:
        sug_list = spellcheck["suggestions"]

        if len(sug_list) > 1 and isinstance(sug_list[1], dict):
            sug_data = sug_list[1].get("suggestion", [])

            # Verificar que haya sugerencias y que sean strings
            if sug_data and isinstance(sug_data[0], str):
                suggestion = sug_data[0]   

   
    if not results:
        return render_template('index.html', error="Error conectando con el motor de búsqueda")
    
    # Procesar resultados
    response_data = results.get('response', {})
    highlighting = results.get('highlighting', {})
    
    documents = []
    for doc in response_data.get('docs', []):
        doc_id = doc.get('id')
        snippet = ""
        
        # Obtener snippet con highlighting
        if doc_id in highlighting:
            hl_content = highlighting[doc_id].get('contenido_es', [])
            if hl_content:
                snippet = hl_content[0]

        # Obtener y formatear el score
        raw_score = doc.get('score', 0)
        
        # Formatear el score para mostrar
        if raw_score:
            # Normalizar a porcentaje (ajusta el máximo según tus scores)
            max_score = 2.0  # Puedes ajustar este valor
            percentage = min(100, int((raw_score / max_score) * 100))
            
            # Crear etiqueta visual
            if percentage >= 80:
                relevance_label = "Muy relevante"
                relevance_class = "relevance-high"
            elif percentage >= 60:
                relevance_label = "Relevante"
                relevance_class = "relevance-medium"
            elif percentage >= 40:
                relevance_label = "Moderado"
                relevance_class = "relevance-low"
            else:
                relevance_label = "Bajo"
                relevance_class = "relevance-very-low"
        else:
            percentage = 0
            relevance_label = "Sin puntuación"
            relevance_class = "relevance-none"

        
        documents.append({
            'id': doc_id,
            'titulo': doc.get('titulo', ['Sin título'])[0] if isinstance(doc.get('titulo'), list) else doc.get('titulo', 'Sin título'),
            'url': doc.get('url', ['#'])[0] if isinstance(doc.get('url'), list) else doc.get('url', '#'),
            'snippet': snippet or doc.get('contenido_es', '')[:200] + '...',
            'score': raw_score,  # Score original
            'score_percentage': percentage,  # Score como porcentaje
            'relevance_label': relevance_label,  # Etiqueta textual
            'relevance_class': relevance_class  # Clase CSS
        })

    # Obtener facetas
    facet_counts = results.get('facet_counts', {})
    facet_fields = facet_counts.get('facet_fields', {})

    # FACETA: dominio
    dominios = facet_fields.get('dominio_facet', [])

    facet_dom = []
    for i in range(0, len(dominios), 2):
        facet_dom.append({
            'valor': dominios[i],
            'conteo': dominios[i+1]
        })

    # FACETA: año
    anios = facet_fields.get('anio', [])

    facet_anio = []
    for i in range(0, len(anios), 2):
        facet_anio.append({
            'valor': anios[i],
            'conteo': anios[i+1]
        })

    # FACETA: tipo de contenido
    tipos = facet_fields.get('tipo_contenido', [])

    facet_tipo = []
    for i in range(0, len(tipos), 2):
        facet_tipo.append({
            'valor': tipos[i],
            'conteo': tipos[i+1]
        })
    
    
    return render_template('results.html',
                         query=query,
                         suggestion=suggestion,
                         documents=documents,
                         facetas_dom=facet_dom,
                         facetas_anio=facet_anio,
                         facetas_tipo=facet_tipo,
                         semantica=usar_semantica,
                         total=response_data.get('numFound', 0),
                         current_page=page,
                         total_pages=(response_data.get('numFound', 0) + 9) // 10)
                         

@app.route('/suggest')
def suggest():
    query = request.args.get('q', '')
    if len(query) < 2:  # Solo sugerir después de 2 caracteres
        return jsonify([])
    
    # Consultar sugerencias a Solr
    params = {
        'suggest.q': query,
        'suggest.count': 5,
        'wt': 'json'
    }
    
    try:
        response = requests.get(f"{SOLR_URL}/suggest", params=params)
        response.raise_for_status()
        data = response.json()
        
        # Extraer términos de sugerencia del nuevo formato
        suggestions = []
        suggester_data = data.get('suggest', {}).get('mySuggester', {})
        if query in suggester_data:
            for item in suggester_data[query].get('suggestions', []):
                suggestions.append(item['term'])  
        
        return jsonify(suggestions)
        
    except Exception as e:
        print(f"Error obteniendo sugerencias: {e}")
        return jsonify([])
    

if __name__ == '__main__':
    app.run(debug=True, port=5000)