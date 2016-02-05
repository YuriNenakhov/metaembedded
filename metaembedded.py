import re
import os

class element:
	def __init__(self, category):
		self.params = {'CATEGORY':category}
		self.elem_type = ''
		self.elem_name = ''

class element_code_generator:
	def __init__(self):
		self.templatepath = "templates/"
		self.configfile = "firmware.gen"
		self.incdir = "./"
		self.srcdir = "./"

	def generate_all(self):
		self.read_config()
		for element_category in self.categories:
			self.template_process(element_category)

	def read_config(self):
		is_element_def = re.compile("^ELEMENT (?P<category>\w+)( (?P<type>\w+))? (?P<params>.*)$")
		self.elements = []
		self.categories = {}
		element_def_str = ''
		with open(self.configfile, 'r') as f:
			while True:
				line = f.readline()
				if not ( is_element_def.search(line) or line == ''):
					element_def_str = element_def_str[:-1]+' '+line
				else:
					element_def = is_element_def.search(element_def_str)
					element_def_str = line
					if element_def:
						self.add_element(element_def)
					if line=='':
						break

	def add_element(self, element_def):
		is_param_def = re.compile("(?P<param>\w+)\s*=\s*(?P<value>[^\s]+)")
		self.categories[element_def.group('category')]=True
		paramdefs = element_def.group('params').split()
		new_element = element(element_def.group('category'))
		if element_def.group('type'):
			new_element.params['TYPE']=element_def.group('type')
		for paramdef_str in paramdefs:
			paramdef = is_param_def.search(paramdef_str)
			if paramdef:
				new_element.params[paramdef.group('param')]=paramdef.group('value')
		if 'TYPE' not in new_element.params:
			new_element.params['TYPE'] = new_element.params['CATEGORY']
		new_element.elem_type = new_element.params['TYPE']
		new_element.elem_name = new_element.params['NAME']
		self.elements.append(new_element)

	def write_file(self, file_description, file_content):
		file_content = '#include "arch_defs.h"\n'+file_content
		if file_description.group('extension') == 'h':
			path = self.incdir
			includeprotection = ("__"+file_description.group('name').upper()+
			 "_"+file_description.group('extension').upper()+"__")
			file_content = (
			 "#ifndef " + includeprotection +
			 "\n#define " + includeprotection +
			 "\n" + file_content +
			 "#endif\n" )
		else:
			path = self.srcdir
		os.makedirs(path, exist_ok=True)
		file_path = path+file_description.group('filename')
		if file_description.group('type')=='AUTOGEN':
			disclaimer = ( "/* Autogenerated by METAEMBEDDED.\n" +
			 " * DO NOT EDIT!\n * All changes will be lost.\n */\n\n" )
		else:
			print("Add project-specific code to "+ file_path)
			disclaimer = ( "/* Autogenerated by METAEMBEDDED.\n" +
			 " * THIS FILE IS EDITABLE. User code is preserved.\n" +
			 " * Add project-specific code to the placeholders.\n" +
			 " * DO NOT REMOVE 'user code' markers or \n" +
			 " * your changes will be lost.\n */\n\n" )
			file_content = self.preserve_user_code(file_content,file_path)
		file_content = disclaimer + file_content
		with open(file_path,"w") as new_f:
			new_f.write(file_content)

	def preserve_user_code(self, file_content, file_path):
		self.is_usercode_statement = re.compile("^(?P<indent>\s*?)//\s*ME USER CODE\s*(?P<tag>.*)$")
		self.usercode_begin = "// --- ME user code for "
		self.usercode_end = "// --- ME user code end"
		old_file = ''
		try:
			with open(file_path, "r") as old_f:
				old_file = old_f.read()
		except IOError:
			pass
		for generated_line in file_content.splitlines():
			if self.is_usercode_statement.search(generated_line):
				usercode_description = self.is_usercode_statement.search(generated_line)
				usercode = ''
				if old_file != '':
					is_usercode = re.compile("^[ \t]*?"+self.usercode_begin+
							usercode_description.group('tag')+
							".*?"+self.usercode_end + "$",
							re.MULTILINE | re.DOTALL)
					if is_usercode.search(old_file):
						usercode = is_usercode.search(old_file).group()
				if usercode == '':
					indent = usercode_description.group('indent') 
					usercode = ( indent + self.usercode_begin + 
								 usercode_description.group('tag') + "\n"+indent+
								 "\n" + indent + self.usercode_end )
				file_content = file_content.replace(generated_line,usercode)
		return file_content

	def generate_statement_process(self, category, gen_description, gen_template):
		result = ''
		gen_template += '\n'
		for element in self.elements:
			gen_entry = ''
			if element.params['CATEGORY'] == category:
				# If type is set:
				if gen_description.group('type')!='':
					if element.params['TYPE'] == gen_description.group('type'):
						gen_entry = gen_template % element.params
						result += gen_entry
				else: # Specific type not set - processing all items in category
					gen_entry = gen_template % element.params
					result += gen_entry
		return result

	def template_process(self,category):
		templatefile = self.templatepath + category + '.template'
		is_file_statement = re.compile("^//\s*======\s*ME FILE (?P<type>\w+) (?P<filename>(?P<name>\w+)\.(?P<extension>\w+))\s*======")
		is_generate_statement = re.compile("^//\s*---\s*ME GENERATE\s*(?P<type>[^\s]*)?\s*---")
		is_generate_end = re.compile("^//\s*---\s*ME GENERATE END\s*---")
		is_script_statement = re.compile("^//\s*---\s*ME SCRIPT\s*---")
		is_script_end = re.compile("^//\s*---\s*ME SCRIPT END\s*---")
		file_description = None
		self.out = ''
		with open(templatefile, 'r') as template:
			while True: # PROCESS TEMPLATE
				line = template.readline()
				if is_file_statement.search(line) or line=='': # start of a new file or template end
					if file_description: # file write was in progress
						self.write_file(file_description,self.out)
					self.out = ''
					if line=='': # TEMPLATE EOF
						break # STOP TEMPLATE PROCESSING
					else:
						file_description = is_file_statement.search(line)
				elif is_generate_statement.search(line): # start generate statement
					generate_description = is_generate_statement.search(line)
					generate_template = ''
					while True: # PROCESS LOCAL GENERATOR
						gen_line = template.readline()
						if is_generate_end.search(gen_line):
							break # STOP LOCAL GENERATOR PROCESSING
						else:
							generate_template += gen_line
					self.out += self.generate_statement_process(category, generate_description, generate_template)
				elif is_script_statement.search(line): # start script statement
					script_code = ''
					while True: # PROCESS LOCAL GENERATOR
						script_line = template.readline()
						if is_script_end.search(script_line):
							break # STOP LOCAL GENERATOR PROCESSING
						else:
							script_code += script_line
					exec(script_code)
				else:
					self.out += line

design = element_code_generator()
design.generate_all()
input("Press Enter to continue...")
