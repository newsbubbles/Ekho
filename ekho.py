import urllib.request
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re
from playsound import playsound
import os
import os.path
import math

from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer
from gensim.summarization.summarizer import summarize

import threading
import time
import sys

import hashlib
import pickle
import json
import itertools

# Gets a web page
# renders voice wav files and plays them in order per sentence
# todo:
#	-add useragent to get requests
#	put the summarization system back in as an option
#	store md5 hashes of sentences with tokenized count stats
#		filter out all high count/url pieces
#		this way the sysetm will begin to ignore all non-unique 
ua = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0"
stotal = 0
rcount = 0
pcount = 0
ready = False

class Renderer (threading.Thread):
	def __init__(self, txt):
		threading.Thread.__init__(self)
		self.txt = txt
	def run(self):
		renderall(self.txt)

class Player (threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	def run(self):
		playloop()

class HashIndex():
	def __init__(self, url):
		urlp = urlparse(url)
		host = urlp.netloc
		self.url = url
		self.host = host
		self.index = {}
		self.series = []
		self.max = 0
		self.min = 99999999
		self.fn = 'index/' + host + '.obj'
		self.load()
		print(self.toJson())
	def save(self):
		fh = open(self.fn, 'wb+') 
		pickle.dump(self.index, fh)
		fh.close()
	def load(self):
		if os.path.isfile(self.fn):
			fh = open(self.fn, 'rb')
			self.index = pickle.load(fh)
			#print(json.dumps(self.index))
			fh.close()
			self.initMax()
	def initMax(self):
		for i, v in self.index.items():
			if v > self.max:
				self.max = v
			if v < self.min:
				self.min = v
	def toJson(self):
		return json.dumps(self.index)
	def gethex(self, txt):
		md5 = hashlib.md5()
		md5.update(txt.encode())
		return md5.hexdigest()
	def add(self, txt):
		h = self.gethex(txt)
		if h not in self.index:
			self.index[h] = 1
			self.series.append(h)
		else:
			self.index[h] += 1
			if self.index[h] > self.max:
				self.max = self.index[h]
			if self.index[h] < self.min:
				self.min = self.index[h]
	def size(self):
		return len(self.index)
	def range(self):
		return self.max - self.min
	def get(self, txt):
		h = self.gethex(txt)
		return self.index[h]
	def val(self, ind):
		return self.index[self.series[ind]]
	def exists(self, txt):
		h = self.gethex(txt)
		return self.index.has_key(h)
	def sortedIndex(self):
		return {key: val for key, val in sorted(self.index.items(), key = lambda ele: ele[1], reverse = True)} 
	def score(self ,md5):
		s = self.size()
		if self.max > 1:
			mean = self.index[md5] / self.max
			#n = math.floor(s / 2);
			#median = next(islice(iter(self.sortedIndex()), n, n+1))
			return mean
		else:
			return 0.0
	def getScore(self, txt):
		h = self.gethex(txt)
		return self.score(h)
	def isCommon(self, txt):
		h = self.gethex(txt)
		if h not in self.index:
			return False
		else:
			return self.score(h) > 0.618

def play(txt):
	wav = synthesizer.tts(txt)
	fname = "render/current.wav"
	synthesizer.save_wav(wav, fname)
	playsound(fname)

def summ(txt):
	return summarize(txt).replace('\n', ' ')

def cleantext(txt):
	txt = txt.replace('"', '').replace("\n", "#!")
	txt = re.sub('\\)|\\(|\\||\\\\|/|:|;|“|”|\\*|<|>|\\r|\' | \'|\\-|\\&|»| ', ' ', txt)
	txt = re.sub(' +', ' ', txt)
	txt = txt.replace(". . ", " ")
	txt = re.sub(' +', ' ', txt)
	txt = txt.replace(". . ", " ")
	txt = txt.replace(" .", ".")
	txt = re.sub('\\.([A-Z])', '. \\1', txt)
	return txt

def getSentences(txt):
	a = re.split("\\. |\\?|!", txt)
	la = len(a)
	if la > 0:
		return a
	else:
		return [a]
	#txt.split('. ')

def getAllSentences(txt):
	a = txt.split("#!")
	o = []
	n = 0
	for i in a:
		s = i.strip()
		w = s.split(" ")
		l = len(s)
		wl = len(w)
		if l > 5 and wl > 0:
			print("-->> " + s)
			ta = getSentences(s)
			print(ta)
			for v in ta:
				c = v.replace('.','').strip()
				cl = len(c)
				print("... " + str(cl) + " ... " + c)
				if cl > 0:
					hashindex.add(c)
					print("\tcount: " + str(hashindex.get(c)) + ", score: " + str(hashindex.getScore(c)))
					if not hashindex.isCommon(c):
						print(str(n) + ">> " + c)
						o.append(c)
						n += 1
	hashindex.save()
	print(hashindex)
	return o

def render(txt, num):
	wav = synthesizer.tts(txt)
	fname = "render/" + str(num) + ".wav"
	synthesizer.save_wav(wav, fname)

def renderall(txt):
	global rcount, stotal, unrendered
	txt = cleantext(txt)
	s = getAllSentences(txt)
	stotal = len(s)
	for i, v in enumerate(s):
		print(">>> Rendering " + str(rcount) + "...")
		render(v, i)
		rcount += 1
		ready = True

def playloop():
	global pcount, rcount, stotal, ready, hashindex
	while pcount < stotal or ready == False:
		print(str(pcount) + " / " + str(rcount))
		if pcount < rcount and rcount > 0:
			print(">>> Playing " + str(pcount) + "...")
			playsound("render/" + str(pcount) + ".wav")
			pcount += 1
		else:
			time.sleep(1)
		if pcount >= stotal:
			break

def go(txt):
	r = Renderer(txt)
	p = Player()
	r.start()
	p.start()


def getPageData(url):
	urlp = urlparse(url)
	host = urlp.netloc
	print('Fetching page from ' + host)
	#"https://www.cnbc.com/2021/02/20/apple-facebook-microsoft-battle-to-replace-smartphone-with-ar.html"
	req = urllib.request.Request(url, data=None, headers={'User-Agent': ua})
	uf = urllib.request.urlopen(req)
	html = uf.read().decode('utf-8')

	soup = BeautifulSoup(html, "html.parser")
	txt = soup.get_text()
	lin = soup.find_all('a')
	links = []
	for i, v in enumerate(lin):
		if len(v.text) > 0 and 'href' in v.attrs:
			print("Link: " + v.text)
			links.append([v.text.strip(), v.attrs['href']])
	return (txt, links)

ar = len(sys.argv)
if (ar == 1):
	print("Please use a URL as the first argument")
	quit()

url = sys.argv[1]
#txt = cleantext(txt)
#txt2 = summ(txt)
#print(txt2)
hashindex = HashIndex(url)
print(hashindex.index)


path = '/home/osiris/.local/share/tts/'

model_path = path + 'tts_models--en--ljspeech--tacotron2-DCA/model_file.pth.tar'
config_path = path + 'tts_models--en--ljspeech--tacotron2-DCA/config.json'
vocoder_path = path + 'vocoder_models--en--ljspeech--mulitband-melgan/model_file.pth.tar'
vocoder_config_path = path + 'vocoder_models--en--ljspeech--mulitband-melgan/config.json'

synthesizer = Synthesizer(model_path, config_path, vocoder_path, vocoder_config_path, False)
#playall(txt2)

(txt, links) = getPageData(url)
go(txt)
