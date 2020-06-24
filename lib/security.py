# -*- coding: utf-8 -*-

import json, logging

from hashlib import md5

class secuUrl:

	def __init__(self, url, user = None, salt = None, way = None):
		#receive whole url
		if user == None:
			self.key = ''
			self.complete_url = url
			self.split(url)
		else:
			#new url
			self.github_url = url
			self.url_path = '/github/' + way + '/' + self.github_url[self.github_url.find('github.com') + 10:].strip('\n').strip('/')
			self.repo_name = self.url_path[self.url_path.rfind('/') + 1:]
			self.user = user
			self.salt = salt
			self.key = ''

	def get_key(self):
		try:
			with open('resources/key', 'r') as keyFile:
				keyJson = json.load(keyFile)
				self.key = keyJson[self.user]
		except KeyError:
			logging.error('User not found')
			return 1

	def sign_url(self):
		hash_string = '{}{}{}'.format(self.salt, self.url_path, self.key)
		self.signum = md5(hash_string.encode()).hexdigest()
		
	def split(self, url):
		self.url_path = url[:url.find('?')]
		self.salt = self.url_path[self.url_path.rfind('/') + 1: ]
		self.url_path = self.url_path[ :self.url_path.rfind('/')]
		self.url_args = url[url.find('?') + 1:]

		self.url_args_dict = json.loads('{"' + self.url_args.replace('&', '","').replace('=', '":"') + '"}')
		self.user = self.url_args_dict['user']
		self.sig_rece = self.url_args_dict['dict']

		self.github_url = 'https://github.com' + self.url_path[self.url_path.find('/', 8):]
		self.repo_name = self.url_path[self.url_path.rfind('/') + 1:]

	def form_args(self):
		self.url_args = "user={}&dict={}".format(self.user, self.signum)

	def form_url(self):
		if self.key == '':
			if self.get_key() == 1:
				#wrong user
				return 1
			self.sign_url()
		self.form_args()
		self.complete_url = "{}/{}?{}".format(self.url_path, self.salt, self.url_args)
		return self.complete_url

	def authen(self):
		if self.key == '':
			if self.get_key() == 1:
				return False
			self.sign_url()
		
		if self.sig_rece == self.signum:
			return True
		else:
			return False
