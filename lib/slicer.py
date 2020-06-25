# -*- coding: utf-8 -*-

import logging, hashlib, os, json

import lib.global_var

PIECE_SIZE = lib.global_var.DEFAULT_PIECE_SIZE
MAX_CONNECTION = lib.global_var.DEFAULT_MAX_CONNECTION
CACHED_COUNTS = lib.global_var.CACHED_COUNTS


class slicer(object):
	file_parts = {}
	processed_piece = 0
	processed_size = 0
	file_done = False
	"""docstring for slicer"""
	def __init__(self, file_path, file_size = None, file_md5 = None):
		logging.debug('starting with piece size ' + str(PIECE_SIZE))
		self.file_path = file_path
		if os.path.isfile(self.file_path):
			self.file_valid = True
			self.filename = self.file_path[self.file_path.rfind('/') + 1:]
			cmd_result = os.popen('md5sum ' + self.file_path)
			self.md5sum = cmd_result.readline().split()[0]
			self.file_size = os.path.getsize(file_path)
			self.file_counts = int(self.file_size / PIECE_SIZE)
			self.split()
		else:
			self.file_valid = False
			self.file_size = file_size

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
			if id in self.file_parts:
				return self.file_parts.pop(id)
			else:
				if os.path.isfile(self.file_path):
					tmp = data_piece(self.file_path, id)
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
				while (len(self.file_parts) < CACHED_COUNTS and self.processed_size < self.file_size):
					if self.processed_piece < self.file_counts - 1:
						data = fp.read(PIECE_SIZE)
					else:
						data = fp.read()
						self.file_done = True
					self.file_parts[self.processed_piece] = data_piece(self.file_path, self.processed_piece, data, len(data))
					self.processed_piece += 1
					self.file_size += len(data)

	def merge(self, piece):
		data_buffer = ''
		self.file_parts[piece.id] = piece
		while self.processed_piece in self.file_parts:
			if self.file_parts[self.processed_piece].check_integrity():
				data += self.file_parts[self.processed_piece].data
			else:
				self.file_parts.pop(self.processed_piece)
				if len(data):
					with open(self.file_path, 'ab') as fp:
						fp.write(data)
				raise Exception(['PIECE BROKE', self.processed_piece])
			self.processed_size += self.file_parts[self.processed_piece].size
			self.processed_piece += 1
			self.file_parts.pop(self.processed_piece)
		with open(self.file_path, 'a') as fp:
			fp.write(data)
		if self.processed_piece == self.file_counts:
			self.file_done = True

	def get_missed_parts(self):
		self.missed_parts = []
		for i in range(self.processed_piece, self.processed_piece + CACHED_COUNTS):
			if not i in file_parts:
				self.missed_parts.append[i]
		return self.missed_parts



class data_piece(object):
	integrity = None
	"""docstring for data_piece"""
	def __init__(self, file_path, id, data = None, piece_size = PIECE_SIZE, piece_MD5 = None):
		self.file_path = file_path
		self.id = id
		if data != None:
			self.data = data
			self.data_MD5 = hashlib.md5(data).hexdigest()
		else:
			self.data = None
		self.size = piece_size

		if piece_MD5 != None:
			self.target_MD5 = piece_MD5
			self.integrity = (self.target_MD5 == self.data_MD5)

	def check_integrity(self):
		if self.integrity != True and self.data != None and self.target_MD5 != None:
			self.md5sum = hashlib.md5(self.data).hexdigest()
			self.integrity = (self.target_MD5 == self.data_MD5)
		elif self.data == None:
			self.integrity = False
		else:
			self.integrity = True

	def get_piece(self):
		if self.data != None:
			return self.data
		else:
			if os.path.isfile(self.file_path):
				with open(self.file_path, 'rb') as fp:
					fp.seek(PIECE_SIZE * self.id, 0)
					self.data = fp.read(self.size)
					return self.data
			else:
				return 1