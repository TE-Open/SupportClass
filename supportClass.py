import os
import inspect
import ast
import weakref
import json
import dataclasses

class ConfigMem:
	@dataclasses.dataclass
	class ConfigItem:
		#this class represents a configuration item
		name: str
		isList: bool
		type: type
		value: ... #the value of a configuration item can be of any type

	def __init__(self, name, configItems, configDir, configFile = "", owner = None, autoSync = False, versionRequired = True):
		#the configuration memory class is used to easily save and load configurations to and from text files
		self.dirPath = configDir
		self.hasFile = (configFile != "")
		self.baseName = configFile
		self.name = name
		self.fullName = name
		self.version = None
		self.owner = None if (owner is None) else weakref.proxy(owner)
		self.autoSync = bool(autoSync) if (not owner is None) else False
		self.versionRequired = bool(versionRequired)
		#build the item dictionary, if the configuration item list is valid
		self.itemDict = {}
		if not type(configItems) in (tuple, list): raise TypeError("CONFLIST", self.name + " - Configuration items argument is not a list")
		for confItem in configItems:
			if not type(confItem) in (tuple, list): raise TypeError("ITEMLIST", self.name + " - One of the configuration items is not a list")
			if not (len(confItem) == 4): raise ValueError("ITEMLEN", self.name + " - One of the configuration items has the wrong number of elements")
			#configuration items must have four elements : item key, item list signal, item type, and starting value
			#attempt to convert the provided value to the desired type
			isList = bool(confItem[1])
			if isList:
				#if the item list depth is greater than 0, it is a list. attempt to convert it
				try:
					itemVal = ConfigMem._convertListValueType(confItem[3], confItem[2])
				except (TypeError, ValueError, OverflowError) as e:
					raise TypeError("ITEMTYPE", self.name + " - The starting value for the " + confItem[0] + " configuration item does not match the item type") from e
			else:
				try:
					itemVal = confItem[2](confItem[3]) if (not confItem[2] is None) else confItem[3]
				except (TypeError, ValueError, OverflowError) as e:
					raise TypeError("ITEMTYPE", self.name + " - The starting value for the " + confItem[0] + " configuration item does not match the item type") from e
			#check that the item name matches an existing variable in the owner object, and create it if required
			if (not self.owner is None) and (not confItem[0] in self.owner.__dict__):
				#create the new attribute in the owner class
				setattr(self.owner, confItem[0], itemVal)
			#copy the information into the releveant dictionaries
			self.itemDict[confItem[0]] = ConfigMem.ConfigItem(name = confItem[0], isList = isList, type = confItem[2], value = itemVal)

	def __repr__(self):
		return ("ConfigMem - " + self.fullName)

	def load(self, version = None):
		#this function tries to read the configuration file, if any, and load it into the configuration dictionary
		if not self.hasFile: raise RuntimeError("NOFILENAME", self.name + " - No configuration file name specified")
		if self.versionRequired and ((version is None) or (version == "")): raise RuntimeError("NOVERSION", self.name + " - Configuration version must not be empty")
		versionStr = "" if (version is None) else str(version)
		name = self.baseName + versionStr
		configFilePath = os.path.join(self.dirPath, name + ".txt")
		if not os.path.isfile(configFilePath): raise IOError("NOFILE", self.name + " - Configuration file not found at " + configFilePath)
		#load the confuguration file into the configuration dictionary
		if (os.path.getsize(configFilePath) != 0):
			#open the file and attempt to load it into the value dicionary with JSON
			#get the file contents
			file = open(configFilePath, "r")
			configStr = file.read()
			file.close()
			#read the contents as JSON
			try:
				newValDict = json.loads(configStr)
			except Exception as e:
				raise RuntimeError("FILEFORMAT", self.name + " - Configuration file is not in JSON format") from e
			#check if there are mismatch between the configuration keys and the file keys
			fileKeySet = set(newValDict.keys())
			confKeySet = set(self.itemDict.keys())
			missingKeys = tuple(confKeySet - fileKeySet)
			if (len(missingKeys) > 0): print(f"{self.name} - The following configuration keys were not found in the configuration file: {", ".join(missingKeys)}")
			unknownKeys = tuple(fileKeySet - confKeySet)
			if (len(unknownKeys) > 0): print(f"{self.name} - The following unknown keys were found in the configuration file: {", ".join(unknownKeys)}")
			commonKeys = tuple(confKeySet & fileKeySet)
			#check that all modified fields have the correct type
			for key in commonKeys:
				if self.itemDict[key].isList:
					valid = ConfigMem._checkListValueType(newValDict[key], self.itemDict[key].type)
				else:
					valid = (type(newValDict[key]) == self.itemDict[key].type) if (not self.itemDict[key].type is None) else True
				if not valid: raise TypeError("ITEMTYPE", self.name + " - Item " + key + " is of incorrect type in configuration file")
			self.fullName = self.name + ("" if (version is None) else (" " + versionStr))
			self.version = None if (version is None) else versionStr
			for key in commonKeys: self.itemDict[key].value = newValDict[key] #update the items with the new values
			if self.autoSync: self.loadDefault()
			return True
		return False

	def save(self, version = None):
		#this function saves the current configuration to a text file
		if not self.hasFile: raise RuntimeError("NOFILENAME", self.name + " - No configuration file name specified")
		#check that the version is not empty
		if self.versionRequired and ((version == "") or ((version is None) and (self.version is None))): raise RuntimeError("NOVERSION", self.name + " - Configuration version must not be empty")
		#if there is a version specified, switch the configuration file name to match
		if not version is None:
			versionStr = str(version)
			self.version = versionStr
			self.fullName = self.name + " " + versionStr
		fileName = self.baseName + ("" if ((version is None) or (self.version is None)) else self.version)
		#get the configuration JSON string
		if self.autoSync: self.saveDefault()
		configStr = json.dumps({key:self.itemDict[key].value for key in self.itemDict})
		#open or create the configuration file, then write the configuration to it
		configFilePath = os.path.join(self.dirPath, fileName + ".txt")
		file = open(configFilePath, "w")
		file.write(configStr)
		file.close()

	def get(self, itemName):
		#this function tries to get a configuration item from the dictionary
		if itemName in self.itemDict:
			return self.itemDict[itemName].value
		else:
			raise NameError("ITEMNAME", self.name + " - Cannot find configuration item " + itemName)

	def set(self, itemName, newVal):
		#this function puts the provided new value into the item of the given name, if the type matches
		if not itemName in self.itemDict: raise NameError("ITEMNAME", self.name + " - Cannot find configuration item " + itemName)
		#assign the new value to the dictionary, if it is correct
		self.itemDict[itemName].value = self._getValidValue(itemName, newVal)

	def loadDefault(self):
		#this function loads all the current configuration item values into the their associated variables
		if self.owner is None: raise RuntimeError("NOOWNER", "This configuration object has no associated owner")
		itemNames = list(self.itemDict.keys())
		for itemName in itemNames:
			self.owner.__dict__[itemName] = self.itemDict[itemName].value

	def saveDefault(self):
		#this function tries to save all associated variable values into their respective configuration item values
		if self.owner is None: raise RuntimeError("NOOWNER", "This configuration object has no associated owner")
		itemNames = list(self.itemDict.keys())
		for itemName in itemNames:
			self.itemDict[itemName].value = self._getValidValue(itemName, self.owner.__dict__[itemName])

	def _getValidValue(self, itemName, newVal):
		#this function checks that the provided value is of the correct type for the associated item, and converts it if necessary
		if self.itemDict[itemName].isList:
			try:
				itemVal = ConfigMem._convertListValueType(newVal, self.itemDict[itemName].type)
			except (TypeError, ValueError, OverflowError) as e:
				raise TypeError("ITEMTYPE", self.name + " - The new value for the " + itemName + " configuration item does not match the item type, or the list is of the wrong depth") from e
		else:
			try:
				itemVal = self.itemDict[itemName].type(newVal) if ((not self.itemDict[itemName].type is None) and (type(newVal) != self.itemDict[itemName].type)) else newVal
			except (TypeError, ValueError, OverflowError) as e:
				raise TypeError("ITEMTYPE", self.name + " - The new value for the " + itemName + " configuration item does not match the item type") from e
		return itemVal

	def show(self, mustPrint = False):
		#this function either prints or returns a string containing all the configuration items and values
		configStr = f"{self.fullName}\n{"\n".join([f"{itemName} : {self.itemDict[itemName].value}" for itemName in list(self.itemDict.keys())])}"
		if mustPrint:
			print(configStr)
		else:
			return configStr

	def _checkListValueType(valList, valType):
		#this function checks that all base elements in the supplied list are of the supplied type,
		if (valType is None): return True
		for i in range(len(valList)):
			if type(valList[i]) != valType: return False
		return True
		return False

	def _convertListValueType(valList, valType):
		#this function attemtps to convert all base elements in the supplied list to the supplied type, if necessary
		if (valType is None): return valList
		newValList = [None] * len(valList)
		for i in range(len(valList)):
			newValList[i] = valType(valList[i]) if (type(valList[i]) != valType) else valList[i]
		return tuple(newValList) if (type(valList) == tuple) else newValList

class DoBase:
	def __init__(self):
		#this is a base class to add the do function to a derived class
		#find all class functions and store them
		funcL = []
		for member in inspect.getmembers(self):
			if inspect.ismethod(member[1]) and (member[0] != "do") and (member[0][0] != "_"):
				funcL.append(member[1])
		self.__funcT = tuple(funcL)
		#create the do command request string
		self.__doCmdStr = ""
		for i in range(len(self.__funcT)):
			self.__doCmdStr += (str(i) + " : " + self.__funcT[i].__name__ + ("\n" if ((i + 1) % 3 == 0) else "  -  "))
		self.__doCmdStr = "\n" + (self.__doCmdStr.strip(" -\n") + "\n\nChoose method :")

	def do(self, cmd = None):
		#this function helps quickly accessing the main functions in the class
		if cmd is None:
			#get a command if none was given
			print(self.__doCmdStr)
			cmd = input()
		#check the command is a valid index in the function list
		if (type(cmd) == str):
			cmd = cmd.strip().lower()
			if not cmd.isnumeric():
				print("\nCommand must be a number or nothing")
				return None
		cmd = int(cmd)
		if (cmd < 0) or (cmd >= len(self.__funcT)):
			print ("\nValid command index is between 0 and " + str(len(self.__funcT) - 1))
			return None
		#select function and ask for arguments, if needed
		func = self.__funcT[cmd]
		fSig = inspect.signature(func)
		argCount = len(fSig.parameters)
		if (argCount == 0):
			#if the function has no arguments (other than self), call it immediately
			print("\nCalling " + func.__name__)
			return func()
		else:
			#if the function ha arguments, request them
			print("\n---" + func.__name__ + " function ---\ninput arguments : " + str(fSig) + "\n")
			args = input().strip().split(" ")
			#build the argument list
			argList = [0] * argCount
			keyT = tuple(fSig.parameters.keys())
			#populate the list with the default if there are any, and get the count pf required arguments
			reqArgCount = 0
			for i in range(argCount):
				if not fSig.parameters[keyT[i]].default == inspect.Parameter.empty:
					argList[i] = fSig.parameters[keyT[i]].default
					if reqArgCount == 0: reqArgCount = i
			if reqArgCount == 0: reqArgCount = argCount
			#go through the supplied arguments and fill the argument list
			pos = 0
			boolD = {"true":True, "t":True, "false":False, "f":False}
			for arg in args:
				if (arg != ""):
					#if the argument is not empty, see if it is named or positional
					argArr = arg.split("=")
					argPos = -1
					if len(argArr) == 2:
						#argument is named
						if argArr[0] in keyT:
							#check argument name is valid
							argPos = keyT.index(argArr[0])
							argVal = argArr[1]
					else:
						#argument is positional
						argPos = pos
						argVal = argArr[0]
						reqArgCount -= 1
						pos += 1
					#if the argument position is too high, exit
					if argPos >= argCount:
						print("\nToo many arguments for function " + func.__name__)
						return None
					#if there was a valid argument, store it in the argument list
					if argPos != -1:
						#attempt conversions
						if argVal[0] in ("[", "("):
							argVal = ast.literal_eval(argVal)
						elif argVal.isnumeric():
							#if the provided argument is numerical convert to int
							argVal = int(argVal)
						else:
							#otherwise attempt float conversion
							try:
								argVal = float(argVal)
							except (ValueError, OverflowError):
								#and finally boolean conversion before simply returning the string value
								argVal = boolD.get(argVal.lower(), argVal)
								#if the value is still a string, and if the first 5 characters are "self.", then try to find an instance variable with the correct name, and substitute it instead
								if (type(argVal) == str) and (len(argVal) > 5) and (argVal[0:5] == "self."):
									if argVal[5:] in self.__dict__:
										argVal = self.__dict__[argVal[5:]]
						argList[argPos] = argVal
			#call the function with arguments, if there are any, and if none of them are missing
			if reqArgCount <= 0:
				print("\nCalling " + func.__name__ + " with arguments " + str(argList) + "\n")
				return func(*argList)
			else:
				print("\nAbort " + func.__name__ + " call : missing " + str(reqArgCount) + " arguments\n")
				return None

class VSetBase:
	def __init__(self, varCol):
		#this is a base class to add the vset (variable set) function to a derived class
		self.__varCount = len(varCol)
		#store the names, diminutives, and types in the supplied variable collection
		varName = [""] * self.__varCount
		varNameDim = [""] * self.__varCount
		varNameLow = [""] * self.__varCount
		varNameDimLow = [""] * self.__varCount
		varType = [None] * self.__varCount
		for i in range(self.__varCount):
			varName[i] = varCol[i][0]
			if not varName[i] in self.__dict__: raise Exception("\"" + varName[i] + "\" is not a variable in " + self.__class__.__name__ + " class")
			varNameLow[i] = varName[i].lower()
			varNameDim[i] = varCol[i][1]
			varNameDimLow[i] = varNameDim[i].lower()
			varType[i] = varCol[i][2]
		self.__varCol = {"name" : tuple(varName), "namelow" : tuple(varNameLow), "namedim" : tuple(varNameDim), "namedimlow" : tuple(varNameDimLow), "type" : tuple(varType)}

	def vset(self):
		#this function helps quickly assign new values to the variables stored in the variable collection
		vsetStr = "Input new values for variable :\n"
		for i in range(self.__varCount):
			vsetStr += (self.__varCol["name"][i] + "/" + self.__varCol["namedim"][i] + " = " + str(self.__dict__[self.__varCol["name"][i]]) + ("\n" if ((i + 1) % 4 == 0) else "  ---  "))
		vsetStr = vsetStr.strip(" -\n") + "\n"
		print(vsetStr)
		#get the user input
		cmdStr = input()
		cmdArr = cmdStr.strip().split(" ")
		#for each commnad, check that they are either positional (no "=" sign in the command"), or if they are named, that the name correspond to valid name or diminutive
		pos = 0
		varChange = [False] * self.__varCount
		varVal = [None] * self.__varCount
		boolD = {"true":True, "t":True, "false":False, "f":False}
		hasValid = False
		for cmd in cmdArr:
			if (cmd != ""):
				#if the argument is not empty, see if it is named or positional
				varArr = cmd.split("=")
				if len(varArr) == 2:
					#argument is named
					varl = varArr[0].lower()
					varPos = (self.__varCol["namelow"].index(varl) if (varl in self.__varCol["namelow"]) else (self.__varCol["namedimlow"].index(varl) if (varl in self.__varCol["namedimlow"]) else -1))
					val = varArr[1]
				else:
					#argument is positional
					varPos = pos
					val = varArr[0]
					pos += 1
				#if the argument position is too high, exit
				if varPos >= self.__varCount:
					print("\nToo many values. There are only " + str(self.__varCount) + " variables")
					return
				#if there was a valid argument, store it in the argument list
				if varPos != -1:
					#attempt conversions according to the associated type of the variable
					if self.__varCol["type"][varPos] == bool:
						#if it is a boolean, try to convert it using the boolean value dictionary
						vall = val.lower()
						if not vall in boolD:
							print("Cannot convert supplied value for " + self.__varCol["name"][varPos] + " to bool")
							return
						varVal[varPos] = boolD[vall]
					elif self.__varCol["type"][varPos] in (list, tuple):
						#if it is a list, try to convert it via literal evaluation
						valid = False
						if val[0] in ("[", "("):
							try:
								varVal[varPos] = ast.literal_eval(val)
								valid = True
							except Exception:
								pass
						if not valid:
							print("Cannot convert supplied value for " + self.__varCol["name"][varPos] + " to a list or tuple")
							return
					else:
						#otherwise attempt to convert it according to the type
						try:
							varVal[varPos] = self.__varCol["type"][varPos](val)
						except Exception:
							print("Cannot convert supplied value for " + self.__varCol["name"][varPos] + " to " + self.__varCol["type"][varPos].__name__)
							return
					varChange[varPos] = True
					hasValid = True
		#check at least one variable was valid
		if not hasValid:
			print("No valid command found")
			return
		#go through the list of variables and change the requested ones
		changedStr = ""
		for i in range(self.__varCount):
			if varChange[i]:
				changedStr += self.__varCol["name"][i] + ", "
				self.__dict__[self.__varCol["name"][i]] = varVal[i]
		print("Changed values for variables " + changedStr.strip(", "))