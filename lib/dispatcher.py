# -*- coding: utf-8 -*-

import logging, threading, queue, http.client, socket

import lib.slicer, lib.global_var, lib.secuUrl

PIECE_SIZE = lib.global_var.DEFAULT_PIECE_SIZE
MAX_CONNECTION = lib.global_var.DEFAULT_MAX_CONNECTION
CACHED_COUNTS = lib.global_var.CACHED_COUNTS

class dispatcher(object):
	data_queue = []
	resend_queue = []
	resent_queue = []
	processed_piece = 0
	"""docstring for dispatcher"""
	def __init__(self, tunnel, file_path, file_size = None, file_md5 = None):
		self.tunnel = tunnel
		self.file_path = file_path
		if file_size == None:
			self.slicer = lib.slicer.slicer(self.file_path)
		else:
			self.slicer = lib.slicer.slicer(self.file_path, file_size, file_md5)
		
	def send(self):
		self.tunnel.settimeout(5)
		while self.processed_piece < self.slicer.file_counts:
			while (len(self.data_queue) < MAX_CONNECTION and len(self.slicer.file_parts)):
				if len(self.resend_queue) > 0:
					self.data_queue.append(self.resend_queue[0])
					self.send_message(self.slicer.get_piece(self.resend_queue[0]))
					self.resend_queue.pop(0)
				else:
					send_piece = self.slicer.get_piece()
					self.send_message(send_piece)
					self.data_queue.append(send_piece.id)
			try:
				recvData = self.tunnel.recv(102400).decode()
				while len(recvData) > 2:
					msg = confirmMessage(recvData[:recvData.find('GET',3)])
					recvData = recvData[recvData.find('GET',3):]
					if msg.status == 'done':
						self.remove_done(msg.packet_id)
						print(msg.packet_id, end=' ')
						self.processed_piece += 1
					elif msg.status == 'lost':
						self.remove_done(msg.packet_id)
						self.resend_queue.append(msg.packet_id)
				self.data_queue.sort()
				try:
					if self.data_queue[0] + MAX_CONNECTION < self.data_queue[1]:
						self.resend_queue.append(self.data_queue[0])
						self.data_queue.pop(0)
				except IndexError:
					pass
			except socket.timeout:
				#resend all
				self.resend_queue.extend(self.data_queue)
				self.data_queue.clear()

	def remove_done(self, piece_id):
		try:
			self.data_queue.remove(piece_id)
		except ValueError:
			pass

	def send_message(self, piece):
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
		while not self.slicer.file_done:
			try:
				response = self.tunnel.getresponse()
				piece_id = int(response.getheader('Content-id'))
				piece_size = int(response.getheader('Content-Length'))
				piece_MD5 = response.getheader('Content-MD5')
				piece_data = response.read()
				#print(len(piece_data))
				piece = lib.slicer.data_piece(self.slicer.file_path, piece_id, piece_size, piece_data, piece_MD5)
				
				url = ""
				try:
					self.slicer.merge(piece)
					print(piece_id, end=' ')
					url = '/confirm/{}'.format(piece_id)
					self.execute_queue(True, piece_id)
					self.tunnel.request('GET', url)
				except Exception as e:
					if e[0] == 'PIECE BROKE':
						self.execute_queue(False, e[1])
	
				
				for ids in self.slicer.get_missed_parts():
					if ids != piece_id:
						self.execute_queue(False, ids)
			except http.client.BadStatusLine:
				for ids in self.slicer.get_missed_parts():
					self.execute_queue(False, ids)

	def execute_queue(self, if_done, piece_id):
		if if_done:
			if piece_id in self.resend_queue:
				self.resend_queue.remove(piece_id)
		else:
			try:
				if not piece_id in self.resend_queue:
					self.resend_queue.append(piece_id)
					url = '/lost/{}'.format(piece_id)
					self.tunnel.request('GET', url)
				elif piece_id in self.resent_queue:
					url = '/lost/{}'.format(piece_id)
					self.tunnel.request('GET', url)
					self.resent_queue.remove(piece_id)
				else:
					self.resent_queue.append(piece_id)
			except http.client.CannotSendRequest:
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
				self.packet_id = int(self.url_parts[-1])
				self.status = 'lost'
			elif self.url_parts[-2] == 'confirm':
				self.packet_id = int(self.url_parts[-1])
				self.status = 'done'
			else:
				self.status = 'error'
				