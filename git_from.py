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
host = 'localhost'
host_port = 10652
github_url = sys.argv[1]

def write_status(repo_name, status):
	logJson = {}
	with open('logs/gits_client.json', 'r') as logFile:
		logJson = json.load(logFile)
	if repo_name in logJson:
		logJson[repo_name]['status'] = status
	else:
		logJson[repo_name] = {}
		logJson[repo_name]['status'] = status
	with open('logs/gits_client.json', 'w') as logFile:
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

		filename = response.getheader('Filename')
		file_size = int(response.getheader('Filesize'))
		file_MD5 = response.getheader('File-MD5')

		receiver = lib.dispatcher.dispatcher(httpClient, filename, file_size, file_MD5)
		logging.debug('Filename: {}, file size: {}, file md5: {}'.format(filename, file_size, file_MD5))
		receiver.receive()
		result = 'done'

	except Exception as e:
		logging.error(e)
		result = 'failed'
	finally:
		if httpClient:
			httpClient.close()

	return result

def main():
	url_path = github_url[github_url.find('github.com') + 10:].strip('\n')
	repo_name = github_url[github_url.rfind('/') + 1:]

	LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
	logging.basicConfig(filename='logs/github_proxy_client.log', level=logging.DEBUG, format=LOG_FORMAT)

	#gitMd5 = hashlib.md5(url_path).hexdigest()
	if os.path.isfile('logs/gits_client.json'):
		gits = {}
		with open('logs/gits_client.json', 'r') as gitsJson:
			gits = json.load(gitsJson)
		if repo_name in gits:
			if gits[repo_name]['status'] == 'done':
				logging.info('already get back ' + github_url)

			elif gits[repo_name]['status'] == 'lost':
				act = input('lost on the server, clone the repo again? (Y/n):')
				if (act == 'y' or act == 'Y'):
					logging.info('restart job ' + github_url)
					result = postJob()
					write_status(repo_name, result)

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
						logging.info('get back ' + github_url)
						result = getGit()
						write_status(repo_name, result)
			else:
				logging.info('get back ' + github_url)
				result = getGit()
				write_status(repo_name, result)
		else:
			logging.info('new job ' + github_url)
			result = postJob()
			write_status(repo_name, result)
	else:
		logging.info('first job ' + github_url)
		with open('logs/gits_client.json', 'w') as gitsJsonFile:
			gits = {}
			gits['description'] = 'client log for jobs'
			json.dump(gits, gitsJsonFile)
		postJob()

main()