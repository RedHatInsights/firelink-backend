from flask import Flask, request, Response
import requests
import logging

app = Flask(__name__, static_url_path=None, static_folder=None)
logging.basicConfig(level=logging.DEBUG)

def proxy_request(url):
    app.logger.debug(f"Proxying request to {url}")
    resp = requests.request(
        method=request.method,
        url=url,
        headers={key: value for (key, value) in request.headers if key != 'Host'},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
        stream=True)  # Enable streaming

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]

    if 'chunked' in resp.headers.get('Transfer-Encoding', ''):
        return Response(resp.iter_content(chunk_size=1024), resp.status_code, headers)
    else:
        return Response(resp.content, resp.status_code, headers)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def catch_all(path):
    if path.startswith('api/'):
        return proxy_request(f'http://127.0.0.1:5000/{path}')
    else:
        return proxy_request(f'http://127.0.0.1:3000/{path}')

if __name__ == '__main__':
    app.run(port=8080)
