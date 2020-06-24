# -*- coding: utf-8 -*-

import http.client
import hashlib
import urllib
import random
import json, logging

import sys, os, threading

from lib.security import secuUrl

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
		result = response.read().decode("utf-8")
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
		return 'cloning'
	elif result == 400:
		return 'cloning'
	elif result == 404:
		return 'lost'
	else:
		return 'error'


def getGit():
	salt = str(random.randint(32768, 65536))
	url_info = secuUrl(github_url, user, salt, 'repo')
	pass

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
					result = postJob()
					write_status(repo_name, result)
			elif gits[repo_name]['status'] == 'cloning':
				logging.info('update status ' + github_url)
				result = jobStatus()
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