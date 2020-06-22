# -*- coding: utf-8 -*-

import http.client
import hashlib
import urllib
import random
import json

import sys,os

def main(github_url):
	url_path = github_url[github_url.find('github.com') + 10:].strip('\n')
	gitMd5 = hashlib.md5(url_path).hexdigest()
	if os.path.isfile('gits.json'):
		gits = {}
		with open('gits.json', 'r') as gitsJson:
			gits = json.load(gitsJson)
		if gitMd5 in gits:
			if gits[gitMd5]['status'] == 'done':
				print('already get back ', github_url)
			elif gits[gitMd5]['status'] == 'lost':
				act = input('lost on the server, clone the repo again? (Y/n):')
				if (act == 'y' or act == 'Y'):
					result = postJob(github_url)
				with open('gits.json', 'w') as gitsJson:
					gits[gitMd5]['status'] = result
			elif gits[gitMd5]['status'] == 'failed':
				act = input('failed last copy, continue? (Y/n):')
				if (act == 'y' or act == 'Y'):
					result = postJob(github_url)
				with open('gits.json', 'w') as gitsJson:
					gits[gitMd5]['status'] = result
			else:
				result = getGit(url_path)
				with open('gits.json', 'w') as gitsJson:
					gits[gitMd5]['status'] = result
	else:
		with open('gits.json', 'w') as gitsJson:
			gits[gitMd5]['status'] = 'starting'

main(sys.argv[1])