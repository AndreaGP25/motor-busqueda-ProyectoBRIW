import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
import re

class SimpleCrawler:
    def __init__(self, delay=1):
        self.delay = delay 
        self.visited = set()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; AcademicCrawler/1.0)'
        })
    
    def extract_content(self, soup):
        """Extrae contenido limpio de la página"""
        # Eliminar scripts y styles
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        
        title = soup.title.string.strip() if soup.title else ""
        
        text = soup.get_text()
        
        # Limpiar texto
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = ' '.join(chunk for chunk in chunks if chunk)
        
        return title, clean_text
    
    def extract_links(self, soup, base_url):
        """Extrae y normaliza enlaces"""
        links = []
        for link in soup.find_all('a', href=True):
            full_url = urljoin(base_url, link['href'])
            
            parsed = urlparse(full_url)
            normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                normalized_url += f"?{parsed.query}"
            
            if self.is_valid_url(normalized_url):
                links.append(normalized_url)
        
        return links
    
    def crawl_page(self, url):
        try:
            print(f"Visitando: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Verificar que es HTML
            if 'text/html' not in response.headers.get('content-type', ''):
                return None, []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            title, content = self.extract_content(soup)
            
            # Extraer enlaces normalizados
            links = self.extract_links(soup, url)
            
            page_data = {
                'id': url,  
                'titulo': title,
                'contenido_es': content,
                'url': url,
                'dominio': urlparse(url).netloc
            }
            

            # Extraer año (solo años válidos: 1900–2099)
            match = re.search(r'\b(19[0-9]{2}|20[0-9]{2})\b', content)
            if match:
                page_data['anio'] = int(match.group())

            tipo = "desconocido"
            titulo_l = title.lower()

            if "noticia" in titulo_l or "news" in titulo_l:
                tipo = "noticia"
            elif "blog" in url.lower():
                tipo = "blog"
            elif "wiki" in url.lower():
                tipo = "articulo"
            elif "encyclopedia" in url.lower():
                tipo = "articulo"
            else:
                tipo = "pagina"

            page_data['tipo_contenido'] = tipo


            self.visited.add(url)
            return page_data, links
        
        except Exception as e:
            print(f"Error crawleando {url}: {e}")
            return None, []
        
    
    def is_valid_url(self, url):
        parsed = urlparse(url)
        
        # Excluir tipos de archivo no deseados
        excluded_extensions = ['.pdf', '.jpg', '.png', '.gif', '.zip']
        excluded_keywords = ['/print', '/pdf', '/download', '/share']
        
        return (parsed.scheme in ['http', 'https'] and 
                parsed.netloc and 
                url not in self.visited and
                not any(url.endswith(ext) for ext in excluded_extensions) and
                not any(keyword in url.lower() for keyword in excluded_keywords))
    
    def crawl_site(self, start_url, max_pages=10):
        """Crawlea un sitio empezando desde start_url"""
        to_visit = [start_url]
        all_data = []
        
        while to_visit and len(all_data) < max_pages:
            current_url = to_visit.pop(0)
            
            if current_url in self.visited:
                continue
                
            page_data, new_links = self.crawl_page(current_url)
            
            if page_data:
                all_data.append(page_data)
                # Agregar nuevos enlaces a la lista (solo del mismo dominio)
                start_domain = urlparse(start_url).netloc
                for link in new_links:
                    if (urlparse(link).netloc == start_domain and 
                        link not in self.visited and 
                        link not in to_visit):
                        to_visit.append(link)
            
            time.sleep(self.delay) 
        
        return all_data

def send_to_solr(documents, solr_url="http://localhost:8983/solr/mi_core_es"):
    """Envía documentos a Solr y reconstruye sugerencias"""
    update_url = f"{solr_url}/update?commit=true"
    
    try:
        response = requests.post(
            update_url,
            json=documents,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        print(f"✓ {len(documents)} documentos enviados a Solr")
        
        return True
    except Exception as e:
        print(f"Error enviando a Solr: {e}")
        return False

# USO DEL CRAWLER
if __name__ == "__main__":
    crawler = SimpleCrawler(delay=2)  # 2 segundos entre requests
    
    start_url = "https://es.wikipedia.org/wiki/Gato"  
    
    print("Iniciando crawler...")
    pages_data = crawler.crawl_site(start_url, max_pages=5)
    
    print(f"\nSe encontraron {len(pages_data)} páginas")
    
    if pages_data:
        success = send_to_solr(pages_data)
        if success:
            print("Crawling completado y datos enviados a Solr")
        else:
            print("Error enviando datos a Solr")
    
    # Guardar también en archivo JSON por seguridad
    with open('datos_crawled.json', 'w', encoding='utf-8') as f:
        json.dump(pages_data, f, ensure_ascii=False, indent=2)
    print("Datos guardados en 'datos_crawled.json'")