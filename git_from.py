# -*- coding: utf-8 -*-

import http.client
import hashlib
import urllib
import random
import json, logging

import sys, os, threading

from lib.security import secuUrl
import lib.dispatcher

user = 'yk'
#host = 'github.smyk323.gq'
#host = 'localhost'
#host = 'www.cmjk123.tk'
host = 'www.acceforyk.cn'
host_port = 12497
github_url = sys.argv[1]

auto_start = None
act = 'n'
retry = 0

abspath = os.path.abspath('.')
#repo_path = '/root/github_proxy/repo/'
repo_path = os.path.join(abspath, 'repo/')
log_path = os.path.join(abspath, 'logs/')
json_path = os.path.join(log_path, 'gits_client.json')

if not os.path.exists(repo_path):
	os.makedirs(repo_path)
if not os.path.exists(log_path):
	os.makedirs(log_path)
if not os.path.isfile(json_path):
	logJson = {}
	logJson['description'] = 'This file stores jobs on client. If you don\'t know what everything means, DON\'T CHANGE ANYTHING!!!'
	with open(json_path, 'w') as fp:
		json.dump(logJson, fp)

def write_status(repo_name, status):
	logJson = {}
	with open(json_path, 'r') as logFile:
		logJson = json.load(logFile)
	if repo_name in logJson:
		logJson[repo_name]['status'] = status
	else:
		logJson[repo_name] = {}
		logJson[repo_name]['status'] = status
	with open(json_path, 'w') as logFile:
		json.dump(logJson, logFile)

def postJob():
	salt = str(random.randint(32768, 65536))
	url_info = secuUrl(github_url, user, salt, 'clone')

	myurl = url_info.form_url()
	logging.debug("POST url: " + myurl)

	httpClient = None
	result = None
	try:
		httpClient = http.client.HTTPConnection(host, host_port)
		httpClient.request('POST', myurl)
		
		# response是HTTPResponse对象
		response = httpClient.getresponse()
		result = response.status
		logging.debug("get response: " + result)

	except Exception as e:
		logging.error(e)
	finally:
		if httpClient:
			httpClient.close()

	if result == 200:
		return 'cloning'
	else:
		return 'error'

def jobStatus():
	salt = str(random.randint(32768, 65536))
	url_info = secuUrl(github_url, user, salt, 'clone')

	myurl = url_info.form_url()
	logging.debug("GET status url: " + myurl)

	httpClient = None
	result = None
	try:
		httpClient = http.client.HTTPConnection(host, host_port)
		httpClient.request('GET', myurl)
		
		# response是HTTPResponse对象
		response = httpClient.getresponse()
		result = response.status

	except Exception as e:
		logging.error(e)
	finally:
		if httpClient:
			httpClient.close()

	if result == 200:
		return 'cloned'
	elif result == 400:
		return 'cloning'
	elif result == 404:
		return 'lost'
	else:
		return 'error'


def getGit():
	salt = str(random.randint(32768, 65536))
	url_info = secuUrl(github_url, user, salt, 'repo')
	myurl = url_info.form_url()
	logging.debug("GET url: " + myurl)

	httpClient = None
	result = None
	try:
		httpClient = http.client.HTTPConnection(host, host_port)
		httpClient.request('GET', myurl)
		
		# response是HTTPResponse对象
		response = httpClient.getresponse()
		result = response.status

		if result == 200:
			filename = response.getheader('Filename')
			file_size = int(response.getheader('Filesize'))
			file_MD5 = response.getheader('File-MD5')
			body = response.read()
	
			receiver = lib.dispatcher.dispatcher(httpClient, filename, file_size, file_MD5)
			logging.debug('Filename: {}, file size: {}, file md5: {}'.format(filename, file_size, file_MD5))
			receiver.receive()
			result = 'done'
		else:
			result = 'failed'

	except ValueError as e:
		logging.error(e)
		result = 'failed'
	finally:
		if httpClient:
			httpClient.close()

	return result

def judge_act():
	global act, retry
	url_path = github_url[github_url.find('github.com') + 10:].strip('\n')
	repo_name = github_url[github_url.rfind('/') + 1:]

	#gitMd5 = hashlib.md5(url_path).hexdigest()
	gits = {}
	with open(json_path, 'r') as gitsJson:
		gits = json.load(gitsJson)
	if repo_name in gits:
		if gits[repo_name]['status'] == 'done':
			print('already get back ' + github_url)
			act = input('job already finished, redo? Warning: redo may overwritten the local file (Y/n):')
			if (act == 'y' or act == 'Y'):
				logging.info('redo job ' + github_url)
				write_status(repo_name, 'redoing')
				judge_act()

		elif gits[repo_name]['status'] == 'lost':
			logging.info('may lost on the server, regain status')
			result = jobStatus()
			if result == 'lost':
				act = input('lost on the server, clone the repo again? (Y/n):')
				if (act == 'y' or act == 'Y'):
					logging.info('restart job ' + github_url)
					result = postJob()
					write_status(repo_name, result)
			else:
				write_status(repo_name, result)
				judge_act()

		elif gits[repo_name]['status'] == 'failed':
			act = input('failed last copy, continue? (Y/n):')
			if (act == 'y' or act == 'Y'):
				logging.info('continue job ' + github_url)
				result = getGit()
				write_status(repo_name, result)

		elif gits[repo_name]['status'] == 'cloning':
			logging.info('update status ' + github_url)
			result = jobStatus()
			logging.info('status updated: ' + result)
			write_status(repo_name, result)
			if result == 'cloned':
				act = input('Cloned on server, get back? (Y/n):')
				if (act == 'y' or act == 'Y'):
					judge_act()

		elif gits[repo_name]['status'] == 'cloned':
			if act != 'y' and act != 'Y':
				act = input('cloned on server, get repo back? (Y/n):')
			if act == 'y' or act == 'Y':
				logging.info('get back ' + github_url)
				result = getGit()
				write_status(repo_name, result)

		elif gits[repo_name]['status'] == 'redoing':
			result = jobStatus()
			logging.info('status updated: ' + result)
			write_status(repo_name, result)
			if result == 'cloned':
				judge_act()

		elif gits[repo_name]['status'] == 'error':
			result = jobStatus()
			logging.info('status updated: ' + result)
			write_status(repo_name, result)
			retry += 1
			if retry < 3:
				judge_act()
			else:
				logging.error('Failed connecting to the server after tried 3 times')

	else:
		logging.info('new job ' + github_url)
		result = postJob()
		write_status(repo_name, result)


def main():
	global act
	LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
	logging.basicConfig(filename=os.path.join(log_path, 'github_proxy_client.log'), level=logging.DEBUG, format=LOG_FORMAT)
	judge_act()

main()