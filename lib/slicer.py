# -*- coding: utf-8 -*-

import logging, hashlib, os, json

import lib.global_var

PIECE_SIZE = lib.global_var.DEFAULT_PIECE_SIZE
MAX_CONNECTION = lib.global_var.DEFAULT_MAX_CONNECTION
CACHED_COUNTS = lib.global_var.CACHED_COUNTS


class slicer(object):
	cached = True
	data_recv = []
	"""docstring for slicer"""
	def __init__(self, file_path, file_size = None, file_md5 = None):
		logging.debug('starting with piece size ' + str(PIECE_SIZE))
		self.file_parts = {}
		self.processed_piece = 0
		self.processed_size = 0
		self.file_done = False
		self.file_path = file_path
		if os.path.isfile(self.file_path) and file_size == None:
			self.file_valid = True
			self.filename = self.file_path[self.file_path.rfind('/') + 1:]
			cmd_result = os.popen('md5sum ' + self.file_path)
			self.md5sum = cmd_result.readline().split()[0]
			self.file_size = os.path.getsize(file_path)
			self.piece_counts = int(self.file_size / PIECE_SIZE)
			self.split()
		else:
			self.file_valid = False
			self.file_size = int(file_size)
			self.piece_counts = int(self.file_size / PIECE_SIZE)
		
		logging.debug('piece counts ' + str(self.piece_counts))

		self.target_MD5 = None
		if file_md5 != None:
			self.target_MD5 = file_md5

	def check_integrity(self):
		if self.target_MD5 == None:
			logging.debug("no md5 received, can't check integrity")
			self.integrity = True
		if os.path.isfile(self.file_path):
			if self.file_size == os.path.getsize(self.file_path):
				with open(self.file_path, 'r') as fp:
					self.md5sum = hashlib.md5(fp.read()).hexdigest()
				self.integrity = (self.md5sum == self.target_MD5)
				logging.info('integrity check result: ' + self.integrity)
			else:
				logging.warning('file size not match')
				self.integrity = False
		else:
			logging.warning('no file found')
			self.integrity = False
		return self.integrity

	def get_piece(self, id = None):
		self.split()
		if id != None:
			if id in self.file_parts and self.cached:
				return self.file_parts.pop(id)
			else:
				if os.path.isfile(self.file_path):
					tmp = None
					if (PIECE_SIZE * (2 + id) > self.file_size):
						tmp = data_piece(self.file_path, id, self.file_size - PIECE_SIZE * id)
					else:
						tmp = data_piece(self.file_path, id)
					if not self.cached and id in self.file_parts:
						self.file_parts.pop(id)
					tmp.get_piece()
					return tmp
				else:
					return 1
		else:
			try:
				keys = list(self.file_parts.keys())
				keys.sort()
				return self.get_piece(keys[0])
			except IndexError:
				return 1

	def split(self):
		if (len(self.file_parts) < MAX_CONNECTION and not self.file_done):
			with open(self.file_path, 'rb') as fp:
				fp.seek(self.processed_piece * PIECE_SIZE, 0)
				read_size = PIECE_SIZE
				while (len(self.file_parts) < CACHED_COUNTS and self.processed_size < self.file_size):

					if self.processed_piece < self.piece_counts - 1:
						read_size = PIECE_SIZE
					else:
						read_size = self.file_size - self.processed_size
						self.file_done = True

					if self.cached:
						data= fp.read(read_size)
						self.file_parts[self.processed_piece] = data_piece(self.file_path, self.processed_piece, read_size, data)
					else:
						self.file_parts[self.processed_piece] = None
					self.processed_size += read_size
					self.processed_piece += 1

	def merge(self, piece):
		data_buffer = bytes()
		if (piece.id >= self.processed_piece):
			self.file_parts[piece.id] = piece
		file_method = 'ab'
		if self.processed_piece == 0 and os.path.isfile(self.file_path):
			file_method = 'wb'
		while self.processed_piece in self.file_parts:
			if self.file_parts[self.processed_piece].check_integrity():
				data_buffer += self.file_parts[self.processed_piece].data
			else:
				self.file_parts.pop(self.processed_piece)
				if len(data_buffer):
					with open(self.file_path, file_method) as fp:
						fp.write(data_buffer)
				raise Exception(['PIECE BROKE', self.processed_piece])
			self.processed_size += self.file_parts[self.processed_piece].size
			self.data_recv.append(self.file_parts[self.processed_piece].id)
			self.file_parts.pop(self.processed_piece)
			self.processed_piece += 1
		if len(data_buffer):
			with open(self.file_path, file_method) as fp:
				fp.write(data_buffer)
		if self.processed_size == self.file_size:
			self.file_done = True

	def get_missed_parts(self):
		self.missed_parts = []
		end_id = self.processed_piece + MAX_CONNECTION
		if end_id > self.piece_counts:
			end_id = self.piece_counts - 1
		if (self.processed_piece < end_id):
			for i in range(self.processed_piece, end_id):
				if not i in self.data_recv:
					self.missed_parts.append(i)
		return self.missed_parts



class data_piece(object):
	"""docstring for data_piece"""
	def __init__(self, file_path, id, piece_size = PIECE_SIZE, data = None, piece_MD5 = None):
		self.file_path = file_path
		self.id = id
		if data != None:
			self.data = data
			self.data_MD5 = hashlib.md5(self.data).hexdigest()
		else:
			self.data = None
		self.size = piece_size

		self.integrity = None
		if piece_MD5 != None:
			self.target_MD5 = piece_MD5
			self.integrity = (self.target_MD5 == self.data_MD5)

	def check_integrity(self):
		if self.integrity != True and self.data != None and self.target_MD5 != None:
			self.data_MD5 = hashlib.md5(self.data).hexdigest()
			self.integrity = (self.target_MD5 == self.data_MD5)
		elif self.data == None:
			self.integrity = False
		else:
			self.integrity = True
		return self.integrity

	def get_piece(self):
		if self.data != None:
			return self.data
		else:
			if os.path.isfile(self.file_path):
				with open(self.file_path, 'rb') as fp:
					fp.seek(PIECE_SIZE * self.id, 0)
					self.data = fp.read(self.size)
					self.data_MD5 = hashlib.md5(self.data).hexdigest()
					return self.data
			else:
				return 1