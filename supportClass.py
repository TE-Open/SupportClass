from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import os
import weakref
from collections.abc import Callable
from typing import Any, cast


class ConfigMem:
	@dataclasses.dataclass
	class ConfigItem:
		#this class represents a configuration item
		name: str
		isList: bool
		type: type
		isValidClass: bool
		initArgCount: int
		value: Any

		def __repr__(self):
			return f"{self.__class__.__name__}(name={self.name}, value={self.value})"

	def __init__(self, name: str, configItems: tuple[tuple[str, bool, type, Any], ...], owner: object, configDir: str, configFile: str = "", autoSync: bool = False, versionRequired: bool = True):
		#the configuration memory class is used to easily save and load configurations to and from text files
		self.dirPath: str = configDir
		self.hasFile: bool = (configFile != "")
		self.baseFileName: str = configFile
		self.name: str = name
		self.version: str = ""
		self.owner: object = weakref.proxy(owner)
		self.autoSync: bool = bool(autoSync) if (not owner is None) else False
		self.versionRequired: bool = bool(versionRequired)
		#build the item dictionary, if the configuration item list is valid
		self.itemDict: dict = {}
		if not type(configItems) in (tuple, list): raise TypeError("CONFLIST", self.name + " - Configuration items argument is not a list")
		itemVal: Any = None
		for confItem in configItems:
			if not type(confItem) in (tuple, list): raise TypeError("ITEMLIST", self.name + " - One of the configuration items is not a list")
			if not (len(confItem) == 4): raise ValueError("ITEMLEN", self.name + " - One of the configuration items has the wrong number of elements")
			#configuration items must have four elements : item key, item list signal, item type, and starting value
			#checkif the the provided value is of the desired type, or can be converted to it. all builtin types are accepted, as well as classes with specific attributes, and no type
			isList = bool(confItem[1])
			isValidClass = callable(confItem[2]) and (hasattr(confItem[2], "__dataclass_fields__") and hasattr(confItem[2], "serialize"))
			if isList:
				#if the item list depth is greater than 0, it is a list. attempt to convert it
				if len(confItem[3]) == 0:
					itemVal = ()
				else:
					try:
						itemVal = ConfigMem._convertListValueType(confItem[3], confItem[2])
					except (TypeError, ValueError, OverflowError) as e:
						raise TypeError("ITEMTYPE", self.name + " - The starting value for the " + confItem[0] + " configuration item does not match the item type") from e
			else:
				if (confItem[2] is None) or (type(confItem[3]) == confItem[2]):
					itemVal = confItem[3]
				elif isValidClass:
					raise TypeError("ITEMTYPE", self.name + " - The starting value for the " + confItem[0] + " configuration item does not match the item type")
				else:
					try:
						itemVal = confItem[2](confItem[3])
					except (TypeError, ValueError, OverflowError) as e:
						raise TypeError("ITEMTYPE", self.name + " - The starting value for the " + confItem[0] + " configuration item does not match the item type") from e
			#check that the item name matches an existing variable in the owner object, and create it if required
			if (not confItem[0] in self.owner.__dict__):
				#create the new attribute in the owner class
				setattr(self.owner, confItem[0], itemVal)
			#copy the information into the releveant dictionaries
			self.itemDict[confItem[0]] = ConfigMem.ConfigItem(confItem[0], isList, confItem[2], isValidClass, (len(inspect.signature(cast(Callable, confItem[2]).__init__).parameters) - 1) if isValidClass else 0, itemVal)

	def __repr__(self):
		return f"ConfigMem - {self.name + ("" if (self.version == "") else f" {self.version}")}"

	def load(self, version: str | int = "") -> bool:
		#this function tries to read the configuration file, if any, and load it into the configuration dictionary
		if not self.hasFile: raise RuntimeError("NOFILENAME", self.name + " - No configuration file name specified")
		if self.versionRequired and (version == ""): raise RuntimeError("NOVERSION", self.name + " - Configuration version must not be empty")
		configFilePath = os.path.join(self.dirPath, self.getSaveFileName(version))
		if not os.path.isfile(configFilePath): raise OSError("NOFILE", self.name + " - Configuration file not found at " + configFilePath)
		#load the confuguration file into the configuration dictionary
		if (os.path.getsize(configFilePath) != 0):
			#open the file and attempt to load it into the value dicionary with JSON
			#get the file contents
			with open(configFilePath, "r") as file:
				configStr = file.read()
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
				if (self.itemDict[key].type is None): continue #no need to check the type if there isn't one
				if self.itemDict[key].isList:
					if len(newValDict[key]) == 0:
						newValDict[key] = ()
					elif self.itemDict[key].isValidClass:
						if not sum([(len(newVal) == self.itemDict[key].initArgCount) for newVal in newValDict[key]]): raise TypeError("ITEMTYPE", f"{self.name} - Item {key} has wrong number of arguments for its type in configuration file")
						newValDict[key] = tuple([self.itemDict[key].type(*newVal) for newVal in newValDict[key]])
					else:
						if not sum([(type(newVal) == self.itemDict[key].type) for newVal in newValDict[key]]): raise TypeError("ITEMTYPE", f"{self.name} - Item {key} is of incorrect type in configuration file")
				elif self.itemDict[key].isValidClass:
					if not (len(newValDict[key]) == self.itemDict[key].initArgCount): raise TypeError("ITEMTYPE", f"{self.name} - Item {key} has wrong number of arguments for its type in configuration file")
					#convert the new value to the custom data type class
					newValDict[key] = self.itemDict[key].type(*newValDict[key])
				else:
					if not (type(newValDict[key]) == self.itemDict[key].type): raise TypeError("ITEMTYPE", f"{self.name} - Item {key} is of incorrect type in configuration file")
			self.version = str(version)
			for key in commonKeys: self.itemDict[key].value = newValDict[key] #update the items with the new values
			if self.autoSync: self.loadDefault()
			return True
		return False

	def save(self, version: str | int = ""):
		#this function saves the current configuration to a text file
		if not self.hasFile: raise RuntimeError("NOFILENAME", self.name + " - No configuration file name specified")
		#check that the version is not empty
		if self.versionRequired and ((version == "") and (self.version == "")): raise RuntimeError("NOVERSION", self.name + " - Configuration version must not be empty")
		#if there is a version specified, switch the configuration version to match
		if version != "": self.version = str(version)
		#get the configuration JSON string
		if self.autoSync: self.saveDefault()
		def getItemSaveValue(configItem: ConfigMem.ConfigItem):
			#this function returns the supplied configuration item in a form that can be turned to a JSON stringe])
			if configItem.isValidClass: return [val.serialize() for val in configItem.value] if configItem.isList else configItem.value.serialize()
			return configItem.value
		configStr = json.dumps({key:getItemSaveValue(self.itemDict[key]) for key in self.itemDict})
		#open or create the configuration file, then write the configuration to it
		with open(os.path.join(self.dirPath, self.getSaveFileName(version)), "w") as file:
			file.write(configStr)

	def getSaveFileName(self, version: str | int = "") -> str:
		#this function returns the file name for the current config object with the given version
		return self.baseFileName + ("" if ((version == "") and (self.version == "")) else (self.version if (version == "") else str(version))) + ".txt"

	def get(self, itemName: str):
		#this function tries to get a configuration item from the dictionary
		if itemName in self.itemDict: return self.itemDict[itemName].value
		raise NameError("ITEMNAME", self.name + " - Cannot find configuration item " + itemName)

	def set(self, itemName: str, newVal: Any):
		#this function puts the provided new value into the item of the given name, if the type matches
		if not itemName in self.itemDict: raise NameError("ITEMNAME", self.name + " - Cannot find configuration item " + itemName)
		#assign the new value to the dictionary, if it is correct
		self.itemDict[itemName].value = self._getValidValue(itemName, newVal)

	def loadDefault(self):
		#this function loads all the current configuration item values into the their associated variables
		if self.owner is None: raise RuntimeError("NOOWNER", "This configuration object has no associated owner")
		for itemName in self.itemDict:
			self.owner.__dict__[itemName] = self.itemDict[itemName].value

	def saveDefault(self):
		#this function tries to save all associated variable values into their respective configuration item values
		if self.owner is None: raise RuntimeError("NOOWNER", "This configuration object has no associated owner")
		for itemName in self.itemDict:
			self.itemDict[itemName].value = self._getValidValue(itemName, self.owner.__dict__[itemName])

	def _getValidValue(self, itemName: str, newVal: Any):
		#this function checks that the provided value is of the correct type for the associated item, and converts it if necessary
		if self.itemDict[itemName].isList:
			try:
				itemVal = ConfigMem._convertListValueType(newVal, self.itemDict[itemName].type)
			except (TypeError, ValueError, OverflowError) as e:
				raise TypeError("ITEMTYPE", self.name + " - The new value for the " + itemName + " configuration item does not match the item type") from e
		else:
			if (self.itemDict[itemName].type is None) or (type(newVal) == self.itemDict[itemName].type):
				itemVal = newVal
			elif self.itemDict[itemName].isValidClass:
				raise TypeError("ITEMTYPE", self.name + " - The new value for the " + itemName + " configuration item does not match the item type")
			else:
				try:
					itemVal = self.itemDict[itemName].type(newVal)
				except (TypeError, ValueError, OverflowError) as e:
					raise TypeError("ITEMTYPE", self.name + " - The new value for the " + itemName + " configuration item does not match the item type") from e
		return itemVal

	def show(self, mustPrint: bool = False):
		#this function either prints or returns a string containing all the configuration items and values
		configStr = f"{self.name + ("" if (self.version is None) else f" {self.version}")}\n{"\n".join([f"{itemName} : {self.itemDict[itemName].value}" for itemName in list(self.itemDict.keys())])}"
		if mustPrint:
			print(configStr)
		else:
			return configStr

	@staticmethod
	def _convertListValueType(valList, valType):
		#this function attemtps to convert all base elements in the supplied list to the supplied type, if necessary
		if (valType is None): return valList
		if (len(valList) == 0): return ()
		return tuple([(valType[val] if (type(val) != valType) else val) for val in valList])

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
				if fSig.parameters[keyT[i]].default != inspect.Parameter.empty:
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
								if (type(argVal) == str) and (len(argVal) > 5) and (argVal[0:5] == "self.") and (argVal[5:] in self.__dict__): argVal = self.__dict__[argVal[5:]]
						argList[argPos] = argVal
			#call the function with arguments, if there are any, and if none of them are missing
			if reqArgCount <= 0:
				print("\nCalling " + func.__name__ + " with arguments " + str(argList) + "\n")
				return func(*argList)
			else:
				print("\nAbort " + func.__name__ + " call : missing " + str(reqArgCount) + " arguments\n")
				return None