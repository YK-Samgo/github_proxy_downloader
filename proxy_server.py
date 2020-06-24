# -*- coding: utf-8 -*-

import os, socket, json, logging, threading

from multiprocessing import Process,Value

from lib.security import secuUrl

def write_status(repo_name, status):
	logJson = {}
	with open('log/gits_server.json', 'r') as logFile:
		logJson = json.load(logFile)
	if repo_name in logJson:
		logJson[repo_name]['status'] = status
	else:
		logJson[repo_name] = {}
		logJson[repo_name]['status'] = status
	with open('log/gits_server.json', 'w') as logFile:
		json.dump(logJson, logFile)

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
		#body = str(return_code)
		body = '<html>\n<head><title>{} {}</title></head>\n<body bgcolor="white">\n<center><h1>{} {}</h1></center>\n<hr><center>nginx/1.10.3</center>\n</body>\n</html>'.format(return_code, return_message, return_code, return_message)

	response = headline + header + body

	sock.send(response.encode())

def clone_job(sock, method, url_info):
	#repo_path = '/root/github_proxy/repo/'
	repo_path ='repo/'

	if (method == 'POST'):
		if os.path.exists(os.path.join(repo_path, url_info.repo_name)):
			send_response(sock, 200, 'ok')
			os.system('cd {}{} && git fetch && cd .. && tar -czf {}.tar.gz {} && rm -rf {}'.format(repo_path, url_info.repo_name, url_info.repo_name.split('.')[0], url_info.repo_name, url_info.repo_name))
		else:
			os.mkdir(os.path.join(repo_path, url_info.repo_name))
			os.system('cd {} && git init --bare && git remote add origin {}'.format(os.path.join(repo_path, url_info.repo_name), url_info.github_url))
			send_response(sock, 200, 'ok')
			logging.info('clone: start cloning {}', url_info.github_url)
			os.system('cd {}{} && git fetch && cd .. && tar -czf {}.tar.gz {} && rm -rf {}'.format(repo_path, url_info.repo_name, url_info.repo_name.split('.')[0], url_info.repo_name, url_info.repo_name))
	elif (method == 'GET'):
		if os.path.exists(os.path.join(repo_path, url_info.repo_name)):
			logging.debug('clone: request is ongoing')
			send_response(sock, 400, 'Bad Request')
		elif os.path.isfile(os.path.join(repo_path, url_info.repo_name + '.tar.gz')):
			logging.debug('clone: request done')
			send_response(sock, 200, 'ok')
		else:
			logging.debug('clone: repo not found')
			send_response(sock, 404, 'Not Found')

def repo_job(sock, method, url_info):
	repo_path = '/root/github_proxy/repo/'

	if (method == 'GET'):
		if os.path.isfile(os.path.join(repo_path, url_info.repo_name + '.tar.gz')):
			send_response(sock, 200, 'ok')
	elif (method == 'DELETE'):
		if os.path.isfile(os.path.join(repo_path, url_info.repo_name + '.tar.gz')):
			#os.system('rm' + os.path.join(repo_path, url_info.repo_name + '.tar.gz'))
			send_response(sock, 200, 'ok')
	else:
		send_response(sock, 404, 'Not Found')

def handle_client(sock, addr, running):
	data = sock.recv(10240).decode()

	headers = data.split('\r\n\r\n')[0]
	#body = data[data.find('\r\n\r\n') + 4 :]

	headers = headers.split('\r\n')
	request_line = headers[0].split(' ')

	url_info = secuUrl(request_line[1])
	logging.info('From: {}\n\trequest: {}'.format(addr[0], headers[0]))
	#api:POST /github/clone/<url>?<salt>&<md5>
	#api:GET /github/clone/<url>?<salt>&<md5>
	#api:GET /github/repo/<url>?<salt>&<md5>
	#api:DELETE /github/repo/<url>?<salt>&<md5>
	if url_info.authen():
		path_part = url_info.url_path.split('/')[1:]
		if (path_part[0] != 'github'):
			logging.error('wrong url\n{}'.format(headers[1:]))
			send_response(sock, 404, 'Not Found')
		elif (path_part[1] == 'clone'):
			clone_job(sock, request_line[0], url_info)
		elif (path_part[1] == 'repo'):
			repo_job(sock, request_line[0], url_info)
		else:
			logging.error('url fail\n{}'.format(headers[1:]))
			send_response(sock, 404, 'Not Found')
	else:
		logging.error('authen failed\n\t{}'.format(headers[1:]))
		send_response(sock, 404, 'Not Found')

	sock.close()

def main():
	servicePort = 10652
	running = Value('i', 1)

	LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
	logging.basicConfig(filename='logs/github_proxy_server.log', level=logging.DEBUG, format=LOG_FORMAT)

	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.bind(('localhost', servicePort))
	server.listen()

	logging.info('start listenning on {}'.format(servicePort))
	try:
		while running:
			sock, addr = server.accept()
			client_process = Process(target=handle_client, args=(sock, addr, running, ))
			client_process.start()
			sock.close()

	finally:
		server.close()

main()