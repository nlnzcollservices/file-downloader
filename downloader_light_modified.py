#! /usr/bin/env python3


"""
Module to assist with downloading resources from URLs.
NB: When reading the help documentation, you may find it easiest to skip over the whole "class Resources(peewee.Model)" section and pick it back up again at FUNCTIONS.

Main code is a class called "DownloadResource", which attempts to download the resource at a given URL, and also writes an entry to a database about the resource.
Assigns filenames by minting a UUID, but also returns original filenames as parsed from headers and/or URL.

Function "download_file_from_url" runs a single URL through Download Resource, downloads the resource and downloads the new database ID for it.

Function "download_from_list" takes a list, tuple or set of URLs and passes each one to DownloadResource - downloads the resources and returns a list of dictionaries with each original url and its new database ID.

You may wish to first run "start_database" if you want to provide a path for your database, and/or to reset the database before downloading anything (eg for testing).

Function "change_filename" can be run after a resource is downloaded and a DownloadObject has been created. You can use this to change the UUID filename to an alternative of your choosing, including the filename_from_headers or filename_from_url.

"""

from datetime import datetime
import exiftool
import hashlib
import logging
import os
from pathlib import Path
import re
import requests
import subprocess
import time
from urllib.parse import urlparse, urlunparse
import uuid

logging.basicConfig(level=logging.INFO)
# defer initialisation of the db until the path is given by user
# see http://docs.peewee-orm.com/en/latest/peewee/database.html#run-time-database-configuration


class DownloadResource:
    """Attempts to download the resource at a given URL, and also writes attributes about the resource to a database.
    ...


    METHODS
    -------

    get_real_download_url
    get_original_filename_from_url
    get_original_filename_from_request_headers
    download_file
    get_file_metadata
    add_file_extension

    Can be run after creation of object to change filename to user preference:
    change_filename

    """

    def __init__(self, url, directory, collect_html, proxies):
        """
        Parameters
        ----------
        url : str
                URL of reseource to be downloaded
        directory : str, optional
                Location of destination directory. Default is a directory called "content" in the current directory
        collect_html : bool, optional
                Set to True if desired behaviour is to download resource if it is just an HTML page. Default is False: download attempt will fail with error message "Target was webpage - deleted"
        proxies : dict, optional
                Pass a proxies dictionary if it will be required for requests.
        """

        self.download_status = None
        self.datetime = None
        self.message = None
        self.directory = directory
        self.collect_html = collect_html
        self.proxies = proxies
        self.url_original = url
        self.url_final = None
        self.filename_from_headers = None
        self.download_status = None
        self.filename_from_url = None
        self.filename = None
        self.filepath = None
        self.filetype_extension = None
        self.mimetype = None
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        self.md5 = None
        self.size_original = None
        self.filesize = None
        self.md5_original = None
        self.exists = False
        self.jhove_check = False
        # ________________________________________________________________________

        # creates an entry in the Resources table and returns it as "self.record"
        # print("here0")

        self.get_real_download_url()

        # continue if no error with requesting URL
        if self.download_status != False:
            # print("here13")

            self.get_original_filename_from_url()
            # print("here14")
            self.get_original_filename_from_request_headers()
            self.get_original_size_from_headers()
            self.get_original_md5_check_from_headers()
            self.download_file()
            self.get_file_metadata()

        # check file extension is correct if file downloaded and not deleted by collect_html flag setting
        if self.download_status == True:
            self.add_file_extension()

            # log outcome
            if self.mimetype == None:
                logging.warning(
                    f"{self.url_original}: Downloaded unknown file type.\nFinal URL: {self.url_final}.\n{self.filename}"
                )
            else:
                logging.info(
                    f"{self.url_original}: Downloaded {self.mimetype}.\nFinal URL: {self.url_final}.\n{self.filename}"
                )
            if self.message is not None:
                logging.info(self.message)
            #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            if (
                self.filesize
                and self.size_original
                and (self.filesize != self.size_original)
            ):
                logging.warning(
                    f"{self.filesize}: Size of file is not equal to original.{self.size_original}"
                )
                self.download_status = False
        # __________________________________________________________________________________________________________________________________________

        elif self.download_status == False:
            logging.warning(f"{self.url_original}: Failed.")
            if self.url_final != None:
                logging.warning(f"Final URL: {self.url_final}.")
            logging.warning(self.message)
        # this is here in case something somehow makes it through without changing download_status to True or False
        else:
            logging.warning("{self.url_original} NO STATUS SET.")

    def output_as_file(self):

        """Writes the results as file a text file"""

        with open("my_file.txt", "w") as f:
            f.write(
                "[configuration]\nurl_original = {}\nurl_final = {}\ndatetime = {}\ndownload_status = {}\nmessage = {}\nfilename_from_url = {}\nfilename_from_headers = {}\nfilename = {}\ndirectory = {}\nfilepath = {}\nfiletype_extension = {}\nmimetype = {}\nfilesize = {}\nsize_original = {}\nmd5 = {}\noriginal_md5 = {}".format(
                    self.url_original,
                    self.url_final,
                    datetime.now(),
                    self.download_status,
                    self.message,
                    self.filename_from_url,
                    self.filename_from_headers,
                    self.filename,
                    self.directory,
                    self.filepath,
                    self.filetype_extension,
                    self.mimetype,
                    self.filesize,
                    self.size_original,
                    self.md5,
                    self.md5_original,
                )
            )

    def output_as_dictionary(self):

        """Makes dictionary
        Returns:
                my_dictionary(dict) - contains all result information

        """
        my_dictionary = {
            "url_original": self.url_original,
            "url_final": self.url_final,
            "datetime": self.datetime,
            "download_status": self.download_status,
            "message": self.message,
            "filename_from_url": self.filename_from_url,
            "filename_from_headers": self.filename_from_headers,
            "filename": self.filename,
            "directory": self.directory,
            "filepath": self.filepath,
            "filetype_extension": self.filetype_extension,
            "mimetype": self.mimetype,
            "filesize": self.filesize,
            "size_original": self.size_original,
            "md5": self.md5,
            "md5_original": self.md5_original,
        }
        return my_dictionary

    def get_real_download_url(self):
        """Cleans any spaces and trailing slashes from the given URL and resolves any redirects. If it encounters a 302 redirect, it picks up the cookies it will need to resolve the final URL.
        Logs error if unable to retrieve URL.
        """
        user_agent = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36"
        headers = {"User-Agent": user_agent}

        session = requests.Session()
        # print("here1")
        # set proxies for the session if needed
        if self.proxies != None:
            session.proxies.update(self.proxies)

        url_stripped = self.url_original.strip().rstrip("/")
        # print("	here2")
        # check if the URL redirects
        try:
            # print("here3")
            cookies = None
            response = session.head(url_stripped, allow_redirects=True)
            # print("here4")
            # if it encounters a 302 response in the redirect chain, save the cookie
            if response.history:
                # print("here5")
                for resp in response.history:
                    # print("here6")
                    if resp.status_code == 302:
                        cookies = resp.cookies
                # request the final url again with the cookie
                response = session.head(response.url, cookies=cookies)

            self.url_final = response.url

            # print("here 7")

            # get the thing, recording the time
            self.datetime = datetime.now()
            # print("here8")
            self.r = requests.get(
                self.url_final, timeout=(5, 14), cookies=cookies, headers=headers
            )

            # print("here9")

            # print(self.r.status_code)

            self.r.raise_for_status()

        except requests.exceptions.HTTPError as e:
            # print(str(e))
            # print("here10")
            self.download_status = False
            self.message = f"HTTPError: {self.r.status_code}"
        except requests.exceptions.ConnectionError as e:
            # print (e)
            # print("here11")
            self.download_status = False
            self.message = f"Connection failed"
        except requests.exceptions.RequestException as e:
            # print("here12")
            self.download_status = False
            self.message = f"RequestException: {e}"

    def get_original_filename_from_url(self):
        """grabs the bit of the url after the last "/" in the URL path
        (See https://docs.python.org/3/library/urllib.parse.html)
        """
        url_path = urlparse(self.url_final)[2]
        self.filename_from_url = os.path.split(url_path)[-1]

    def get_original_filename_from_request_headers(self):
        """Uses a regex to find the filename in URL headers['Content-Disposition'] if it exists"""
        # ***		# THIS WILL NEED A LOT MORE ROBUST TESTING!
        if "Content-Disposition" in self.r.headers:
            regex = '(?<=filename=")(.*)(?=")'
            m = re.search(regex, self.r.headers["Content-Disposition"])
            if m:
                self.filename_from_headers = m.group(1)
            else:

                self.message = "'Content-Disposition' exists in headers but failed to parse filename"

    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    def get_original_size_from_headers(self):

        """Gets filesize from URL headers['Content-Length'] if it exists"""
        if "Content-Length" in self.r.headers:
            self.size_original = int(self.r.headers.get("Content-Length"))

    def get_original_md5_check_from_headers(self):

        """Gets md5 from URL headers['Content-MD5'] if it exists"""
        if "Content-MD5" in self.r.headers:
            self.md5_original = self.r.headers.get("Content-MD5")

    # __________________________________________________________________________________________________________________________________

    def download_file(self):
        """Downloads the resource, minting a unique filename from a UUID and creating the destination directory first if necessary"""

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        self.filename = str(uuid.uuid4())
        self.filepath = os.path.join(self.directory, self.filename)

        with open(self.filepath, "wb") as f:
            for chunk in self.r.iter_content(100000):
                f.write(chunk)
        self.download_status = True

    def get_file_metadata(self):
        """Uses EXIFtool to get file extension and MIMEtype, then gets md5 hash"""

        # ***	# TODO: put exiftool.exe somewhere where it doesn't need the full path
        with exiftool.ExifTool() as et:
            metadata = et.get_metadata(self.filepath)

        # print(metadata)
        # print('File:FileSize' in metadata)
        # if discarding html pages, this happens here
        if self.collect_html == False:
            if "File:MIMEType" in metadata:
                if metadata["File:MIMEType"] == "text/html":
                    os.remove(self.filepath)

                    self.download_status = False
                    self.message = "Target was webpage - deleted"

                    # get rid of some of the fields written to the db as now longer relevent
                    self.directory, self.filename, self.filepath = None, None, None
                    return

        if "ExifTool:Error" in metadata:
            if self.message == None:
                self.message = "Unknown filetype"
            else:
                self.message = "{message} ; Unknown filetype"
        # print("'File:FileSize' in metadata")
        if "File:FileTypeExtension" in metadata:
            self.filetype_extension = metadata["File:FileTypeExtension"]
        else:
            self.filetype_extension = None
        if "File:MIMEType" in metadata:
            self.mimetype = metadata["File:MIMEType"]
        else:
            self.mimetype = None
        if "File:FileSize" in metadata:

            self.filesize = metadata["File:FileSize"]
            # print(self.filesize)
            # print(type(self.filesize))
            # print("!!!!!!!!!!!!!!!!!!!!!")

        else:
            self.filesize = None
        hash_md5 = hashlib.md5()
        with open(self.filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
                self.md5 = hash_md5.hexdigest()

    def add_file_extension(self):
        """Adds correct file extension as found by EXIFtool to filename"""
        if self.filetype_extension != None:
            new_filepath = os.path.join(
                self.directory,
                self.filename + os.extsep + self.filetype_extension.lower(),
            )
            os.rename(self.filepath, new_filepath)
            self.filepath = new_filepath
            self.filename = Path(self.filepath).name

    def change_filename(
        self,
        rename_from_headers=False,
        rename_from_url=False,
        new_filename=None,
        custom_name=None,
    ):
        # TODO REPLACE THIS
        """Run this method over an existing DownloadObject to change the filename to a string of your choosing.
        Requires a DownloadObject. All other parameters are optional; only one will be actioned, with priority in the order set out below.
        Will not rename to the same name as a file already present in the directory - will return with self.renamed = False.
        ...
        Parameters
        ----------
        self : an existing DownloadObject instance
        rename_from headers : bool, optional
                set to True if you want to give the file the same filename originally found in the resource header
        rename_from_url : bool, optional
                set to True if you want to give the file the same filename originally found in the URL
        new_filename : str, optional
                Pass any filename you like here (including extension)

        Attributes
        ----------
        filename, filepath : str
                Set to new values if succsssful
        renamed : bool
                True if successful, else False. You could use this to retry with a different parameter if unsuccessful (eg if you set to use headers and there was no filename in the headers originally)
        """
        # print("Renaming")
        if self.download_status == True:
            if rename_from_headers == True:
                self.new_filename = self.filename_from_headers
            elif rename_from_url == True:
                self.new_filename = (
                    self.filename_from_url
                )  #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            elif custom_name:
                self.new_filename = custom_name
            if self.new_filename == None:
                logging.warning(
                    "Could not change filename of '{self.filename}' from {self.url_original}: no new filename provided"
                )
                return
            #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            self.new_filepath = os.path.join(self.directory, self.new_filename)
            # print(self.new_filepath)
            if not os.path.exists(self.new_filepath):
                os.rename(self.filepath, self.new_filepath)
                logging.info(
                    f"'{self.filepath}' successfully changed to {self.new_filename}'"
                )
                self.filename = self.new_filename
                self.filepath = self.new_filepath
                self.renamed = True
            # ___________________________________________________________________________________________________________________________________________________________________
            else:
                # print("already here")
                self.exists = True
                logging.warning(
                    f"Could not change filename of '{self.filename}' from {self.url_original}: new name '{new_filename}' already exists in '{self.directory}'"
                )
        else:
            logging.warning(
                f"Could not change filename from {self.url_original} - no file was downloaded"
            )

    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    def jhove_check(self):
        # print(self.filepath)
        command = [r"jhove", self.filepath, "-t", "text"]  # the shell command
        # print(command)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        output, error = process.communicate()
        output = str(output).split(r"\r\n")[1:-1]
        for el in output:
            if "Status" in el:
                if "Well-Formed and valid" in el:
                    self.jhove_check = True

	"""Attempts to download the resource at a given URL, and also writes attributes about the resource to a database.
	...


	METHODS
	-------
	
	get_real_download_url
	get_original_filename_from_url
	get_original_filename_from_request_headers
	download_file
	get_file_metadata
	add_file_extension

	Can be run after creation of object to change filename to user preference:
	change_filename
		
	"""

	def __init__(self, url, directory, collect_html, proxies):
		"""
		Parameters
		----------
		url : str
			URL of reseource to be downloaded
		directory : str, optional
			Location of destination directory. Default is a directory called "content" in the current directory
		collect_html : bool, optional
			Set to True if desired behaviour is to download resource if it is just an HTML page. Default is False: download attempt will fail with error message "Target was webpage - deleted"
		proxies : dict, optional
			Pass a proxies dictionary if it will be required for requests.
		"""

		self.download_status = None
		self.datetime = None
		self.message = None
		self.directory = directory
		self.collect_html = collect_html
		self.proxies = proxies
		self.url_original = url
		self.url_final = None
		self.filename_from_headers = None
		self.download_status = None
		self.filename_from_url = None
		self.filename = None
		self.filepath = None
		self.filetype_extension = None
		self.mimetype = None
		#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
		self.md5 = None
		self.size_original = None
		self.filesize = None
		self.md5_original = None
		self.exists = False
		self.jhove_check = False
#________________________________________________________________________

				
		# creates an entry in the Resources table and returns it as "self.record"
		#print("here0")

		self.get_real_download_url()


		# continue if no error with requesting URL
		if self.download_status != False:
			#print("here13")

			self.get_original_filename_from_url()
			#print("here14")
			self.get_original_filename_from_request_headers()
			self.get_original_size_from_headers()
			self.get_original_md5_check_from_headers()
			self.download_file()
			self.get_file_metadata()

		# check file extension is correct if file downloaded and not deleted by collect_html flag setting
		if self.download_status == True:
			self.add_file_extension()

		# log outcome
			if self.mimetype == None:
				logging.warning(f"{self.url_original}: Downloaded unknown file type.\nFinal URL: {self.url_final}.\n{self.filename}")
			else:
				logging.info(f"{self.url_original}: Downloaded {self.mimetype}.\nFinal URL: {self.url_final}.\n{self.filename}")
			if self.message is not None:
				logging.info(self.message)
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
			if self.filesize and self.size_original and (self.filesize!= self.size_original):
				logging.warning(f"{self.filesize}: Size of file is not equal to original.{self.size_original}")
				self.download_status = False
#__________________________________________________________________________________________________________________________________________

		elif self.download_status == False:
			logging.warning(f"{self.url_original}: Failed.")
			if self.url_final != None:
				logging.warning(f"Final URL: {self.url_final}.")
			logging.warning(self.message)
		# this is here in case something somehow makes it through without changing download_status to True or False
		else:
			logging.warning("{self.url_original} NO STATUS SET.")
		

	def output_as_file(self):

		"""Writes the results as file a text file"""

		with open("my_file.txt" ,"w")  as f:
			f.write("[configuration]\nurl_original = {}\nurl_final = {}\ndatetime = {}\ndownload_status = {}\nmessage = {}\nfilename_from_url = {}\nfilename_from_headers = {}\nfilename = {}\ndirectory = {}\nfilepath = {}\nfiletype_extension = {}\nmimetype = {}\nfilesize = {}\nsize_original = {}\nmd5 = {}\noriginal_md5 = {}".format( self.url_original, self.url_final, datetime.now(), self.download_status, self.message, self.filename_from_url, self.filename_from_headers,   self.filename, self.directory, self.filepath, self.filetype_extension,  self.mimetype, self.filesize, self.size_original, self.md5, self.md5_original))

	def output_as_dictionary(self):

		"""Makes dictionary 
		Returns:
			my_dictionary(dict) - contains all result information

		"""
		my_dictionary =  {"url_original":self.url_original, "url_final":self.url_final,  "datetime" : self.datetime, "download_status" : self.download_status, "message": self.message,  "filename_from_url":self.filename_from_url, "filename_from_headers":self.filename_from_headers, "filename":self.filename, "directory":self.directory, "filepath":self.filepath, "filetype_extension":self.filetype_extension, "mimetype":self.mimetype,"filesize":self.filesize, "size_original":self.size_original, "md5" :self.md5,  "md5_original": self.md5_original}
		return my_dictionary

	def get_real_download_url(self):
		"""Cleans any spaces and trailing slashes from the given URL and resolves any redirects. If it encounters a 302 redirect, it picks up the cookies it will need to resolve the final URL. 
		Logs error if unable to retrieve URL.
		"""
		user_agent = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'
		headers = {'User-Agent': user_agent}

		session = requests.Session()
		#print("here1")
		# set proxies for the session if needed
		if self.proxies != None:
						session.proxies.update(self.proxies)

		url_stripped = self.url_original.strip().rstrip("/")
		#print("	here2")
		# check if the URL redirects
		try:
			#print("here3")
			cookies = None
			response = session.head(url_stripped, allow_redirects=True)
			#print("here4")
			# if it encounters a 302 response in the redirect chain, save the cookie
			if response.history:
				#print("here5")
				for resp in response.history:
					#print("here6")
					if resp.status_code == 302:
						cookies = resp.cookies
				# request the final url again with the cookie
				response = session.head(response.url, cookies=cookies)

			self.url_final = response.url

			#print("here 7")
															
			# get the thing, recording the time
			self.datetime = datetime.now()
			#print("here8")
			self.r = requests.get(self.url_final, timeout=(5,14), cookies= cookies, headers=headers)

			#print("here9")

			#print(self.r.status_code)
			
			self.r.raise_for_status()

		except requests.exceptions.HTTPError as e:
			#print(str(e))
			#print("here10")
			self.download_status = False
			self.message = f"HTTPError: {self.r.status_code}"
		except requests.exceptions.ConnectionError as e:
			#print (e)
			#print("here11")
			self.download_status = False
			self.message = f"Connection failed"
		except requests.exceptions.RequestException as e:
			#print("here12")
			self.download_status = False
			self.message = f"RequestException: {e}"

	def get_original_filename_from_url(self):	
		"""grabs the bit of the url after the last "/" in the URL path
		(See https://docs.python.org/3/library/urllib.parse.html)
		"""
		url_path = urlparse(self.url_final)[2]
		self.filename_from_url = os.path.split(url_path)[-1]


	def get_original_filename_from_request_headers(self):
		"""Uses a regex to find the filename in URL headers['Content-Disposition'] if it exists
		"""
#***		# THIS WILL NEED A LOT MORE ROBUST TESTING!
		if 'Content-Disposition' in self.r.headers:
			regex = '(?<=filename=")(.*)(?=")'
			m = re.search(regex, self.r.headers['Content-Disposition'])
			if m:
				self.filename_from_headers = m.group(1)
			else:

				self.message = "'Content-Disposition' exists in headers but failed to parse filename"
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
	def get_original_size_from_headers(self):

		"""Gets filesize from URL headers['Content-Length'] if it exists
		"""
		if 'Content-Length' in self.r.headers:
			self.size_original = int(self.r.headers.get('Content-Length'))
			

	def get_original_md5_check_from_headers(self):

		"""Gets md5 from URL headers['Content-MD5'] if it exists
		"""
		if 'Content-MD5' in self.r.headers:
			self.md5_original = self.r.headers.get('Content-MD5')
#__________________________________________________________________________________________________________________________________

	def download_file(self):
		"""Downloads the resource, minting a unique filename from a UUID and creating the destination directory first if necessary
		"""

		if not os.path.exists(self.directory): os.makedirs(self.directory)
		self.filename = str(uuid.uuid4())
		self.filepath = os.path.join(self.directory, self.filename)

		with open(self.filepath, 'wb') as f:
			for chunk in self.r.iter_content(100000):
				f.write(chunk)
		self.download_status = True

	def get_file_metadata(self):
		"""Uses EXIFtool to get file extension and MIMEtype, then gets md5 hash
		"""

#***	# TODO: put exiftool.exe somewhere where it doesn't need the full path
		with exiftool.ExifTool() as et:
			metadata = et.get_metadata(self.filepath)

		#print(metadata)
		#print('File:FileSize' in metadata)
		# if discarding html pages, this happens here
		if self.collect_html == False:
			if 'File:MIMEType' in metadata:
				if metadata['File:MIMEType'] == "text/html":
					os.remove(self.filepath)

					self.download_status = False
					self.message = "Target was webpage - deleted"

					# get rid of some of the fields written to the db as now longer relevent
					self.directory, self.filename, self.filepath = None, None, None			
					return

		if 'ExifTool:Error' in metadata:
			if self.message == None:
				self.message = "Unknown filetype"
			else:
				self.message = "{message} ; Unknown filetype"		
		# print("'File:FileSize' in metadata")
		if 'File:FileTypeExtension' in metadata:
			self.filetype_extension = metadata['File:FileTypeExtension']
		else: 
			self.filetype_extension = None
		if 'File:MIMEType' in metadata:
			self.mimetype = metadata['File:MIMEType']
		else:
			self.mimetype = None
		if 'File:FileSize' in metadata:
			
			self.filesize = metadata['File:FileSize']
			# print(self.filesize)
			# print(type(self.filesize))
			# print("!!!!!!!!!!!!!!!!!!!!!")

		else:
			self.filesize = None
		hash_md5 = hashlib.md5()
		with open(self.filepath, "rb") as f:
			for chunk in iter(lambda: f.read(4096), b""):
				hash_md5.update(chunk)
				self.md5 = hash_md5.hexdigest()



	def add_file_extension(self):
		"""Adds correct file extension as found by EXIFtool to filename 
		"""
		if self.filetype_extension != None:
			new_filepath = os.path.join(self.directory, self.filename + os.extsep + self.filetype_extension.lower())
			os.rename(self.filepath, new_filepath)
			self.filepath = new_filepath
			self.filename = str(ntpath.basename(self.filepath))



	def change_filename(self, rename_from_headers=False, rename_from_url=False, new_filename=None, custom_name=None):
		# TODO REPLACE THIS
		"""Run this method over an existing DownloadObject to change the filename to a string of your choosing.
		Requires a DownloadObject. All other parameters are optional; only one will be actioned, with priority in the order set out below.
		Will not rename to the same name as a file already present in the directory - will return with self.renamed = False.
		...
		Parameters
		----------
		self : an existing DownloadObject instance
		rename_from headers : bool, optional
			set to True if you want to give the file the same filename originally found in the resource header
		rename_from_url : bool, optional
			set to True if you want to give the file the same filename originally found in the URL
		new_filename : str, optional
			Pass any filename you like here (including extension)

		Attributes
		----------
		filename, filepath : str
			Set to new values if succsssful
		renamed : bool
			True if successful, else False. You could use this to retry with a different parameter if unsuccessful (eg if you set to use headers and there was no filename in the headers originally)
		"""
		#print("Renaming")
		if self.download_status == True:
			if rename_from_headers == True:
				self.new_filename = self.filename_from_headers
			elif rename_from_url == True:
				self.new_filename = self.filename_from_url#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
			elif custom_name:
				self.new_filename =custom_name
			if self.new_filename == None:
				logging.warning("Could not change filename of '{self.filename}' from {self.url_original}: no new filename provided")
				return
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!		
			self.new_filepath = os.path.join(self.directory, self.new_filename)
			#print(self.new_filepath)
			if not os.path.exists(self.new_filepath):
				os.rename(self.filepath, self.new_filepath)
				logging.info(f"'{self.filepath}' successfully changed to {self.new_filename}'")
				self.filename = self.new_filename
				self.filepath = self.new_filepath
				self.renamed = True
#___________________________________________________________________________________________________________________________________________________________________
			else:
				#print("already here")
				self.exists = True
				logging.warning(f"Could not change filename of '{self.filename}' from {self.url_original}: new name '{new_filename}' already exists in '{self.directory}'")
		else:
			logging.warning(f"Could not change filename from {self.url_original} - no file was downloaded")
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
	def jhove_check(self):
		#print(self.filepath)
		command = [r'jhove',self.filepath,'-t', 'text'] # the shell command
		#print(command)
		process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
		output, error = process.communicate()
		output = str(output).split(r"\r\n")[1:-1]
		for el in output:
			if 'Status' in el:
				if "Well-Formed and valid" in el:
					self.jhove_check =  True

def example():
	directory = r'Y:\ndha\pre-deposit_prod\LD_working\svetlana'
	urls = [r"https://dl.dropboxusercontent.com/s/6d33skud10atywq/Sepia.mp4"]
	for url in urls:
		target_resource = DownloadResource(url, directory, collect_html=False, proxies=None)
		# target_resource.change_filename(rename_from_headers=True)
		dictionary = target_resource.output_as_dictionary()
		print(dictionary)
		# for element in dictionary.keys():
		# 	#print(element)
		# 	print(f"{element}:{dictionary[element]}")
		# if 'filename_from_url' in dictionary.keys():
		# 		target_resource.change_filename(rename_from_url = True)


#_____________________________________________________________________________________________________________________________________________________________________________________________

if __name__ == '__main__':
	example()

def example():
    directory = r"Y:\ndha\pre-deposit_prod\LD_working\svetlana"
    urls = [r"https://dl.dropboxusercontent.com/s/6d33skud10atywq/Sepia.mp4"]
    for url in urls:
        target_resource = DownloadResource(
            url, directory, collect_html=False, proxies=None
        )
        # target_resource.change_filename(rename_from_headers=True)
        dictionary = target_resource.output_as_dictionary()
        print(dictionary)
        # for element in dictionary.keys():
        # 	#print(element)
        # 	print(f"{element}:{dictionary[element]}")
        # if 'filename_from_url' in dictionary.keys():
        # 		target_resource.change_filename(rename_from_url = True)


# _____________________________________________________________________________________________________________________________________________________________________________________________

if __name__ == "__main__":
    example()
