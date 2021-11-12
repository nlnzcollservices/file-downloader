More testing to see whether trimming everything in URL after path ever breaks anything

Testing if Content-Disposition regex ever fails

check that the revised request requests "just work" without passing a proxy dict on the network.

Add some usage examples

Write up requirements including EXIFtool

Work out how to package / bundle w EXIFtool

Add something to check for hash clashes

Compare hashes in directory

add collection name and identifier (uuid)

add option to override filename #use at own risk!

edit change_filename function

add get metadata option

from whiteboard notes:

	for url in my_urls:
	
	md = get_url(url, get_md=True)
	
	my_log.append(md)
	
Log to CSV

Does it need 'IE' awareness (managing multiple files to IE)

table per IE?

Aug 2021
file size 
jhove?
self.message

remove database
needs to handle giving it filenames constructed by the user

sometimes characters in URL/headers(?) are illegal for filenames

module returns objects - external scripts can make use of object attributes

safemover changes filenames - what are the rules it follows?