# -*- coding: utf-8 -*-

import os, socket, json, logging, threading, hashlib

from multiprocessing import Process,Value

from lib.security import secuUrl
import lib.dispatcher

'''
status : cloning, cloned, done, error, failed
'''

#host = 'localhost'
host = '0.0.0.0'
servicePort = 12497

abspath = os.path.abspath('.')
#repo_path = '/root/github_proxy/repo/'
repo_path = os.path.join(abspath, 'repo/')
log_path = os.path.join(abspath, 'logs/')
json_path = os.path.join(log_path, 'gits_server.json')

if not os.path.exists(repo_path):
	os.makedirs(repo_path)
if not os.path.exists(log_path):
	os.makedirs(log_path)
if not os.path.isfile(json_path):
	logJson = {}
	logJson['description'] = 'This file stores jobs on server. If you don\'t know what everything means, DON\'T CHANGE ANYTHING!!!'
	with open(json_path, 'w') as fp:
		json.dump(logJson, fp)


stable_state = ['cloned', 'done']

def read_status(repo_name):
	status = None
	with open(json_path, 'r') as logFile:
		logJson = json.load(logFile)
		if repo_name in logJson:
			status = logJson[repo_name]['status']

	dir_exist = os.path.exists(os.path.join(repo_path, repo_name))
	tar_exist = os.path.isfile(os.path.join(repo_path, repo_name + '.tar.gz'))
	if status in stable_state:
		if dir_exist or not tar_exist:
			status = 'error'
	else:
		if status == 'failed':
			status = 'cloned'
		elif tar_exist:
			status = 'error'
		elif status == 'cloning':
			if not dir_exist:
				status = 'error'
	return status


def write_status(repo_name, status):
	logJson = {}
	if not os.path.isfile(json_path):
		with open(json_path, 'w') as logFile:
			json.dump(logJson, logFile)
	with open(json_path, 'r') as logFile:
		logJson = json.load(logFile)
	if repo_name in logJson:
		logJson[repo_name]['status'] = status
	else:
		logJson[repo_name] = {}
		logJson[repo_name]['status'] = status
	with open(json_path, 'w') as logFile:
		json.dump(logJson, logFile)

def send_response(sock, return_code, return_message, additional_info = None, body = None):
	headline = 'HTTP/1.1 {} {}\r\n'.format(return_code, return_message)

	header = '\r\n'
	if additional_info != None:
		for key, value in additional_info.items():
			header = '{}: {}\r\n{}'.format(key, value, header)
	
	if body == None:
		header = 'Content-Type: text/html\r\n' + header
		#body = str(return_code)
		body = '<html>\n<head><title>{} {}</title></head>\n<body bgcolor="white">\n<center><h1>{} {}</h1></center>\n<hr><center>nginx/1.10.3</center>\n</body>\n</html>'.format(return_code, return_message, return_code, return_message)
		header = 'Content-Length: {}\r\n{}'.format(len(body), header)

	response = headline + header + body
	logging.debug('send response:\n' + response)

	sock.send(response.encode())

def clone_job(sock, method, url_info):
	status = read_status(url_info.repo_name)

	if (method == 'POST'):
		if status == 'cloning' or status in stable_state:
			send_response(sock, 200, 'ok')
			#os.system('cd {}{} && git fetch && cd .. && tar -czf {}.tar.gz {} && rm -rf {}'.format(repo_path, url_info.repo_name, url_info.repo_name.split('.')[0], url_info.repo_name, url_info.repo_name))
		else:
			os.makedirs(os.path.join(repo_path, url_info.repo_name))
			os.system('cd {} && git init --bare && git remote add origin {}'.format(os.path.join(repo_path, url_info.repo_name), url_info.github_url))
			send_response(sock, 200, 'ok')
			write_status(url_info.repo_name, 'cloning')
			logging.info('clone: start cloning ' + url_info.github_url)
			os.system('cd {}{} && git fetch && cd .. && tar -czf {}.tar.gz {} && rm -rf {}'.format(repo_path, url_info.repo_name, url_info.repo_name, url_info.repo_name, url_info.repo_name))
			logging.info('cloned ' + url_info.github_url)
			write_status(url_info.repo_name, 'cloned')
	elif (method == 'GET'):
		if status == 'cloning':
			logging.debug('clone: request is ongoing')
			send_response(sock, 400, 'Bad Request')
		elif status == 'cloned' or status == 'done':
			logging.debug('clone: request done')
			send_response(sock, 200, 'ok')
		else:
			logging.debug('clone: repo not found')
			send_response(sock, 404, 'Not Found')

def repo_job(sock, method, url_info):
	file_path = os.path.join(repo_path, url_info.repo_name + '.tar.gz')

	if (method == 'GET'):
		if os.path.isfile(file_path):
			logging.info('send back: ' + url_info.repo_name + '.tar.gz')
			sender = lib.dispatcher.dispatcher(sock, file_path)
			info = {}
			info['Content-Disposition'] = file_path
			info['Filename'] = url_info.repo_name + '.tar.gz'
			info['File-MD5'] = sender.file_MD5
			info['Filesize'] = sender.slicer.file_size
			send_response(sock, 200, 'ok', info)
			sock.settimeout(5)
			if sender.send():
				write_status(url_info.repo_name, 'failed')
				logging.error('send back job failed: ' + url_info.repo_name)
			else:
				write_status(url_info.repo_name, 'done')
				logging.info('send back job done: ' + url_info.repo_name)
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

	logging.info('From: {}\n\trequest: {}'.format(addr[0], headers[0]))
	url_info = None
	try:
		url_info = secuUrl(request_line[1])
		#api:POST /github/clone/<url>?<salt>&<md5>
		#api:GET /github/clone/<url>?<salt>&<md5>
		#api:GET /github/repo/<url>?<salt>&<md5>&<piece-id>
		#api:DELETE /github/repo/<url>?<salt>&<md5>
		if url_info != None and url_info.authen():
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
	except Exception:
		logging.error('invalid url')
		send_response(sock, 200, 'ok')

	sock.close()

def main():
	running = Value('i', 1)

	LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
	logging.basicConfig(filename=os.path.join(log_path, 'github_proxy_server.log'), level=logging.DEBUG, format=LOG_FORMAT)

	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.bind((host, servicePort))
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