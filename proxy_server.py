# -*- coding: utf-8 -*-

import os, socket, tarfile, hashlib, json

from multiprocessing import Process,Value

def send_response(sock, return_code, return_message, body = None, additional_info = None):
	headline = 'HTTP/1.1 {} {}\r\n'.format(return_code, return_message)

	header = '\r\n'
	if additional_info != None:
		if additional_info['Content-Type'] == 'application/x-tar':
			for key, value in additional_info.getitems():
				header = '{}: {}\r\n{}'.format(key, value, header)
			header = 'Content-Length: {}\r\n{}'.format(os.path.getsize(additional_info['Content-Disposition']), header)
	else:
		header = 'Content-Type: text/html\r\n' + header
		body = '<html>\n<head><title>{} {}</title></head>\n<body bgcolor="white">\n<center><h1>{} {}</h1></center>\n<hr><center>nginx/1.10.3</center>\n</body>\n</html>'.format(return_code, return_message, return_code, return_message)

	response = headline + header + body

	sock.send(response)

def authentic(url):
	key = ''
	with open('key', 'r') as keyFile:
		key = keyFile.read().strip('\n')

	try:
		url_path = url[:url.find('?')]
		url_args = url[url.find('?') + 1:].split('&')

		if hashlib.md5(url_args[0] + url_path + key).hexdigest() == url_args[1]:
			return True
		else:
			return False
	except Exception:
		return False

def repo_job(sock, method, url_path):
	repo_path = '/root/github_proxy/repo/'
	github_url = 'https://github.com' + url_path[url_path.find('clone') + 5:]
	repo_name = url_path[url_path.rfind('/') + 1:]

	if (method == 'GET'):
		if os.path.isfile(repo_path + repo_name + '.tar.gz'):
			send_response(sock, 200, 'ok')
	elif (method == 'DELETE'):
		if os.path.isfile(repo_path + repo_name + '.tar.gz'):
			#os.system('rm' + repo_path + repo_name + '.tar.gz')
			send_response(sock, 200, 'ok')
	else:
		send_response(sock, 404, 'Not Found')

def clone_job(sock, method, url_path):
	repo_path = '/root/github_proxy/repo/'
	github_url = 'https://github.com' + url_path[url_path.find('clone') + 5:]
	repo_name = url_path[url_path.rfind('/') + 1:]

	if (method == 'POST'):
		if os.path.exists(repo_path + repo_name):
			send(sock, 200, 'ok')
			os.system('cd {}{} && git fetch && cd .. && tar -czf {}.tar.gz {} && rm -rf {}'.format(repo_path, repo_name, repo_name.split('.')[0], repo_name, repo_name))
		else:
			os.system('cd {} && mkdir {} && git init --bare && git remote add origin {}'.format(repo_path, repo_name, github_url))
			send(sock, 200, 'ok')
			os.system('cd {}{} && git fetch && cd .. && tar -czf {}.tar.gz {} && rm -rf {}'.format(repo_path, repo_name, repo_name.split('.')[0], repo_name, repo_name))
	elif (method == 'GET'):
		if os.path.exists(repo_path + repo_name):
			send_response(sock, 400, 'Bad Request')
		elif os.path.isfile(repo_path + repo_name + '.tar.gz'):
			send_response(sock, 200, 'ok')
		else:
			send_response(sock, 404, 'Not Found')

def handle_client(sock, running):
	data = sock.recv(10240)

	headers = data[:data.find('\r\n\r\n')]
	#body = data[data.find('\r\n\r\n') + 4 :]

	headers = headers.split('\r\n')
	request_line = headers.split(' ')
	#api:POST /github/clone/<url>?<salt>&<md5>
	#api:GET /github/clone/<url>?<salt>&<md5>
	#api:GET /github/repo/<url>?<salt>&<md5>
	#api:DELETE /github/repo/<url>?<salt>&<md5>
	if authentic(request_line[1]):
		url_path = request_line[1][:request_line[1].find('?')]
		path_part = url_path.split('/')
		if (path_part[0] != 'github'):
			send_response(sock, 404, 'Not Found'):
		elif (path_part[1] == 'clone'):
			clone_job(sock, request_line[0], url_path)
		elif (path_part[1] == 'repo'):
			repo_job(sock, request_line[0], url_path)
		else:
			send_response(sock, 404, 'Not Found')
	else:
		send_response(sock, 404, 'Not Found')

	sock.close()

def main():
	running = Value('i', 1)

	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.bind(('localhost', 10652))
	server.listen()

	try:
		while running:
			sock, addr = server.accept()
			client_process = Process(target=handle_client, args=(sock, running, ))
			client_process.start()
			sock.close()

	finally:
		server.close()

main()