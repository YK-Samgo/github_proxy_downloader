# -*- coding: utf-8 -*-

import logging, threading, queue, http.client, socket, random, time

import lib.slicer, lib.global_var, lib.security

PIECE_SIZE = lib.global_var.DEFAULT_PIECE_SIZE
MAX_CONNECTION = lib.global_var.DEFAULT_MAX_CONNECTION
CACHED_COUNTS = lib.global_var.CACHED_COUNTS

user = 'yk'

class dispatcher(object):
	data_queue = []
	resend_queue = []
	resent_queue = []
	processed_piece = 0
	retry = 0
	"""docstring for dispatcher"""
	def __init__(self, tunnel, file_path, file_size = None, file_MD5 = None):
		self.tunnel = tunnel
		self.file_path = file_path
		if file_size == None:
			self.slicer = lib.slicer.slicer(self.file_path)
			self.file_MD5 = self.slicer.md5sum
		else:
			self.slicer = lib.slicer.slicer(self.file_path, int(file_size), file_MD5)
			self.file_MD5 = file_MD5
		
	def send(self):
		self.tunnel.settimeout(5)
		if_sent = False
		while self.processed_piece < self.slicer.piece_counts and not if_sent:
			try:
				recvData = self.tunnel.recv(102400).decode()
				self.retry = 0
				recvData = recvData.split('\r\n\r\n')
				for request in recvData:
					if len(request) > 1:
						headers = request.split('\r\n')
						request_line = headers[0].split()
						url_info = lib.security.secuUrl(request_line[1])
						if url_info.authen():
							msg = confirmMessage('{} {} {}'.format(request_line[0], url_info.url_path, request_line[2]))
							if msg.status == 'done':
								self.remove_done(msg.piece_id)
								if_sent = True
								self.tunnel.send('HTTP/1.1 200 ok\r\n\r\n'.encode())
								#print(msg.piece_id, end=' ')
								self.processed_piece += 1
							elif msg.status == 'lost':
								self.remove_done(msg.piece_id)
								self.resend_queue.append(msg.piece_id)
							elif msg.status == 'get':
								self.send_piece(self.slicer.get_piece(msg.piece_id))
								self.data_queue.append(msg.piece_id)
			except socket.timeout:
				#resend all
				logging.error('retry {}'.format(self.retry))
				self.retry += 1
				if self.retry == 3:
					logging.error('retry timeout! abort')
					return 1
		return 0

	def remove_done(self, piece_id):
		try:
			self.data_queue.remove(piece_id)
		except ValueError:
			pass

	def send_piece(self, piece):
		logging.debug('send piece {} Length: {}'.format(str(piece.id), len(piece.data)))
		headline = 'HTTP/1.1 200 ok\r\n'

		header = '\r\n'
		header = 'Content-MD5: {}\r\n{}'.format(piece.data_MD5, header)
		#header = 'Content-Encoding: identity\r\n{}'.format(header)
		#header = 'Transfer-Encoding:chunked\r\n{}'.format(header)
		#header = 'Cache-Control: no-cache\r\n{}'.format(header)
		header = 'Content-id: {}\r\n{}'.format(piece.id, header)
		header = 'Content-Length: {}\r\n{}'.format(piece.size, header)

		headers = (headline + header).encode()
		#print(headers, len(piece.data))
		self.tunnel.send(headers + piece.data)

	def receive(self):
		logging.debug("start receive: " + self.file_path)
		print("start receive: " + self.file_path)
		time0 = time.time()
		self.processed_size_last_time = 0
		while not self.slicer.file_done:
			try:
				for id in self.slicer.get_missed_parts():
					logging.debug('request piece ' + str(id))
					self.execute_queue(id)

				logging.debug('waiting for pieces {}'.format(self.slicer.missed_parts))
				response = self.tunnel.getresponse()
				piece_id = int(response.getheader('Content-id'))
				piece_size = int(response.getheader('Content-Length'))
				piece_MD5 = response.getheader('Content-MD5')
				piece_data = response.read()
				#print(len(piece_data))
				piece = lib.slicer.data_piece(self.slicer.file_path, piece_id, piece_size, piece_data, piece_MD5)
				try:
					self.slicer.merge(piece)
					logging.debug('merged ' + str(self.slicer.processed_piece))
					time1 = int(time.time())
					if time1 > time0:
						print('processed: {}KB/{}KB ({}/{}) {} KB/s'.format(int(self.slicer.processed_size / 1024), int(self.slicer.file_size / 1024), self.slicer.processed_piece, self.slicer.piece_counts, int((self.slicer.processed_size - self.processed_size_last_time)/(time1 -time0))), end='', flush=True)
						time0 = time1
						self.processed_size_last_time = self.slicer.processed_size
					#print(piece_id, end=' ')
				except Exception as e:
					logging.debug(e)

			except http.client.BadStatusLine:
				pass
		time1 = time.time()
		print('processed: {}KB/{}KB ({}/{}) {} KB/s'.format(int(self.slicer.processed_size / 1024), int(self.slicer.file_size / 1024), self.slicer.processed_piece, self.slicer.piece_counts, int((self.slicer.processed_size - self.processed_size_last_time)/(time1 -time0))), end='', flush=True)
		salt = str(random.randint(32768, 65536))
		url_info = lib.security.secuUrl('/confirm/{}'.format(self.slicer.piece_counts), user, salt, 'repo')
		url_info.form_url()
		logging.debug('request: ' + url_info.complete_url)
		self.tunnel.request('GET', url_info.complete_url)
		self.tunnel.getresponse()

	def execute_queue(self, id):
		try:
			if not id in self.data_queue:
				salt = str(random.randint(32768, 65536))
				url_info = lib.security.secuUrl('/get/{}'.format(id), user, salt, 'repo')
				url_info.form_url()
				logging.debug('request: ' + url_info.complete_url)
				self.tunnel.request('GET', url_info.complete_url)
				self.data_queue.append(id)
			elif id in self.resend_queue:
				salt = str(random.randint(32768, 65536))
				url_info = lib.security.secuUrl('/get/{}'.format(id), user, salt, 'repo')
				url_info.form_url()
				logging.debug('request again: ' + url_info.complete_url)
				self.tunnel.request('GET', url_info.complete_url)
				self.resend_queue.pop(id)
			else:
				self.resend_queue.append(id)
		except Exception:
			logging.error(Exception)
			pass


class confirmMessage:
	def __init__(self, message):
		self.message = message
		self.headers = self.message.split('\r\n')
		self.method, self.url, self.http_version = self.headers[0].split()
		self.get_status()

	def get_status(self):
		if self.method != 'GET':
			self.status = 'error'
		else:
			self.url_parts = self.url.strip('/').split('/')
			if self.url_parts[-2] == 'lost':
				self.piece_id = int(self.url_parts[-1])
				self.status = 'lost'
			elif self.url_parts[-2] == 'confirm':
				self.piece_id = int(self.url_parts[-1])
				self.status = 'done'
			elif self.url_parts[-2] == 'get':
				self.piece_id = int(self.url_parts[-1])
				self.status = 'get'
			else:
				self.status = 'error'
				