# SupportClass
This is a python module contatining three classe designed as support for other classes.
- ## ConfigMem
  This class is used to create a list of class variables that can be easily saved to or loaded from a text file (which is useful for configurations, hence the name).
  
  Each configuration item is a tuple of the form : (**Name of the item**, **List depth**, **Item type**, **Item value**)\
  **List depth** is an integer representing whether the item is a list, and how nested that list is.\
  A scalar has list depth 0, a simple list has list depth 1, a list of lists has list depth 2, etc...\
   **Item type** is a python type class.
  
  The configuration items have corresponding variables in the owning objects.\
  Saving them to a file is done simply with the save function.
- ## DoBase
  This is a base class that must be inherited from.\
  It adds the do function to a class, which allows you to call any function of the derived class and set its argulents from a command line interface.\
  It is really only useful when using the python interpreter.
- ## VSetBase
  Like DoBase, this is a base class that must be inherited from.\
  It adds the vset function to a class, which allows you to set a number of predermined variables from the command line interface, while checking the input is of the correct type.\
  It is similarily only useful when using the python interpreter.
