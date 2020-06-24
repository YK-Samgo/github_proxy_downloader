# -*- coding: utf-8 -*-

import logging, threading, queue, http.client, socket

import slicer, global_var

PIECE_SIZE = global_var.DEFAULT_PIECE_SIZE
MAX_CONNECTION = global_var.DEFAULT_MAX_CONNECTION
CACHED_COUNTS = global_var.CACHED_COUNTS

class dispatcher(object):
	data_queue = []
	resend_queue = []
	processed_piece = 0
	"""docstring for dispatcher"""
	def __init__(self, tunnel, file_path, ):
		self.tunnel = tunnel
		self.file_path = file_path
		self.slicer = slicer.slicer(self.file_path)
		
	def send(self):
		while self.processed_piece < self.slicer.file_counts:
			while (len(data_queue) < MAX_CONNECTION and not self.slicer.file_done):
				if len(resend_queue) > 0:
					self.send_message(self.slicer.get_piece(resend_queue[0]))
					self.data_queue.append(resend_queue[0])
					resend_queue.pop[0]
			recvData = self.tunnel.recv(102400).decode()
			while len(recvData) > 2:
				msg = confirmMessage(recvData[:recvData.find('GET')])
				recvData = recvData[recvData.find('GET'):]
				if msg.status == 'done':
					self.remove_done(msg.packet_id)
					self.processed_piece += 1
				elif msg.status == 'lost':
					self.remove_done(msg.packet_id)
					self.resend_queue.append(msg.packet_id)
			self.data_queue.sort()
			if self.data_queue[0] + MAX_CONNECTION < self.data_queue[1]:
				self.resend_queue.append(self.data_queue[0])
				self.data_queue.pop(0)

	def remove_done(self, id):
		try:
			self.data_queue.remove(id)
		except ValueError:
			pass

	def send_message(self, piece):
		pass

	def receive(self):
		self.tunnel.getresponse()


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
			self.packet_id = self.url_parts[-1]
			if self.url_parts[-2] == 'lost':
				self.status = 'lost'
			elif self.url_parts[-2] == 'confirm':
				self.status = 'done'
			else:
				self.status = 'error'
				