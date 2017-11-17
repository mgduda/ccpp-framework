#!/usr/bin/env python

# This script does the following:
# 1. Reads in argument variable metadata from the XML files generated by parse_scheme_table.py.
# 2. Reads the calls to the subroutines and saves the actual calling arguments in the "calling_vars" fields of the subroutine namedtuple.
# 3. Performs rudimentary check of argument numbers, attempting to account for optional arguments
# 4. Assigns the calling argument variable with the associated var_metadata_type from the subroutine argument tables.
# 5. Creates a python set (eliminates duplication) of calling argument variables with which to check for longname conflicts.
# 6. Check for longname conflicts by going through the set of calling argument variables and looking for instances where the same calling argument variables is referred to by different longnames in the subroutine argument tables.
# 7. Print a list of calling argument variables and the subroutines in which they are used (critical for putting the necessary metadata into a dycore)
# 8. Print a list of conflicts which includes the calling argument variables, variable longnames, subroutine local variable names, and the name of the subroutine where each variable is used


import argparse  #needed for command line argument filenames
from xml.etree import ElementTree as ET #needed for reading XML
import collections

#set up the command line argument parser
parser = argparse.ArgumentParser()

#the only arguments are a a list of XML files to parse and a list of files with the subroutine calls
parser.add_argument('file', help='paths to XML files generated from scheme tables', nargs='*')
parser.add_argument('--call_file', nargs = '*', action='store', help = 'paths to fortran files that call the schemes')
#parser.add_argument('call_file', help='paths to fortran files that call the schemes', nargs='1' )
args = parser.parse_args()

#set up named tuple types
var_metadata_type = collections.namedtuple('var_metadata_type', 'longname units id rank type description kind intent optional calling_var')
scheme_type = collections.namedtuple('scheme_type', 'name subroutines')
subroutine_type = collections.namedtuple('subroutine_type', 'name arguments calling_vars') #

#each XML file represents one scheme; read in the argument table information from each file
schemes = []
for i in range(len(args.file)):
    filename = args.file[i]

    tree = ET.parse(filename)
    scheme = tree.getroot()

    #multiple subroutines can be associated with each scheme; XML children of each "scheme" are the subroutines
    subroutines = []
    for sub in scheme:
        vars = []
        #XML children of each subroutine are the variable metadata
        for var in sub:
            #get the metadata from the XML fields
            longname = var[0].text
            units = var[1].text
            id = var[2].text
            rank = var[3].text
            type = var[4].text
            description = var[5].text
            kind = var[6].text
            intent = var[7].text
            optional = var[8].text
            #create a var_metadata_type with the variable metadata, leaving the calling var field blank at this point (will be filled in using the subroutine call information)
            var_metadata = var_metadata_type(longname=longname, units=units, id=id, rank=rank, type=type, description=description, kind=kind, intent=intent, optional=optional, calling_var='')
            #put all var_metadata_types into a vars list
            vars.append(var_metadata)
        #append each subroutine_type to a list of subroutines
        subroutines.append(subroutine_type(name = sub.attrib['name'], arguments = vars, calling_vars = []))
    #append each scheme_type to a list of schemes
    schemes.append(scheme_type(name=scheme.attrib['module'], subroutines=subroutines))

#for each file that contains calling information, read the calling argument variables and associate them with a subroutine
for i in range(len(args.call_file)):
    filename = args.call_file[i]

    #read all lines of the file at once
    with (open(filename, 'r')) as file:
        file_lines = file.readlines()

    #look for all of the schemes and subroutine calls in this file
    for scheme in schemes:
        for subroutine in scheme.subroutines:
            sub_found = False
            line_counter = 0
            for line in file_lines:
                if line.lower().find(subroutine.name) >= 0:
                    words = line.split()
                    for j in range(len(words)):
                        #search for the subroutine name and that where the subroutine name is found has the structure "call subroutine_name"
                        if words[j].lower() == subroutine.name and j == 1 and words[j-1].lower() == 'call':
                            sub_found = True
                            print subroutine.name + ' found in file ' + filename + ' at line ' + str(line_counter+1)
                            #grab all the text between the opening and closing () !!!!This section could be made much more robust and be utilized to read the actual fortran files !!!!
                            args_start = line.find('(')
                            args_end = line.rfind(')')
                            args_str = line[args_start+1:args_end]
                            #divide the string by ', ' (not by ',' alone due to commas in array slice syntax - NOTE: this means that the calling syntax should have all variables separated by ', ' and that all array slices don't have whitespace)
                            args = [x.strip(' ') for x in args_str.split(', ')]

                            #since tuples are immutable, create a new one and replace the old one with the calling argument variable information
                            new_tuple = subroutine_type(name = subroutine.name, arguments = subroutine.arguments, calling_vars = args)
                            subroutine = new_tuple


                        if sub_found:
                            break
                line_counter += 1

            if sub_found:
                #determine how many non-optional arguments are in the subroutine
                num_non_optional_arguments = 0
                for k in range(len(subroutine.arguments)):
                    if not (subroutine.arguments[k].optional.lower() == 't' or subroutine.arguments[k].optional.lower() == 'true'):
                        num_non_optional_arguments += 1
                #num_optional_arguments = (len(subroutine.arguments)) - num_non_optional_arguments

                if len(subroutine.calling_vars) < num_non_optional_arguments:
                    #if the number of calling argument variables are less than the number of non-optional arguments, let the user know that there is a problem
                    print 'Too few arguments were supplied in the call to ' + subroutine.name
                    print 'calling arguments: ' + str(len(subroutine.calling_vars))
                    print 'non-optional subroutine arguments: ' + str(num_non_optional_arguments)
                    print subroutine.arguments
                elif len(subroutine.calling_vars) == num_non_optional_arguments:
                    #if the number of calling arguments is the same as the number of non-optional arguments, assume that the arguments are positionally correct and assign the calling variables to the subroutine arguments by ORDER
                    for k in range(len(subroutine.arguments)):
                        new_tuple = var_metadata_type(longname=subroutine.arguments[k].longname, units=subroutine.arguments[k].units, id=subroutine.arguments[k].id, rank=subroutine.arguments[k].rank, type=subroutine.arguments[k].type, description=subroutine.arguments[k].description, kind=subroutine.arguments[k].kind, intent=subroutine.arguments[k].intent, optional=subroutine.arguments[k].optional, calling_var=subroutine.calling_vars[k])
                        subroutine.arguments[k] = new_tuple
                elif len(subroutine.calling_vars) > len(subroutine.arguments):
                    #if there are more calling argument variables supplied than the subroutine expects, let the user know
                    print 'Too many arguments (mandatory + optional) were supplied in the call to ' + subroutine.name
                    print 'calling arguments: ' + str(len(subroutine.calling_vars))
                    print 'subroutine arguments: ' + str(len(subroutine.arguments))
                    print subroutine.calling_vars
                else:
                    #the number of arguments supplied in the call is greater than the number of non-optional arguments but less than the total of non-optional and optional arguments expected by the subroutine; check for optional arguments
                    for k in range(len(subroutine.arguments)):
                        if subroutine.arguments[k].optional.lower() == 't' or subroutine.arguments[k].optional.lower() == 'true':
                            #for optional arguments, look for arguments being passed in with keywords by id; if the id is not found in the calling variables, then optional_calling_var is an empty list
                            optional_calling_var = [s for s in subroutine.calling_vars if subroutine.arguments[k].id in s]
                            if optional_calling_var:
                                optional_calling_var = optional_calling_var[0].split('=')[1]
                                new_tuple = var_metadata_type(longname=subroutine.arguments[k].longname, units=subroutine.arguments[k].units, id=subroutine.arguments[k].id, rank=subroutine.arguments[k].rank, type=subroutine.arguments[k].type, description=subroutine.arguments[k].description, kind=subroutine.arguments[k].kind, intent=subroutine.arguments[k].intent, optional=subroutine.arguments[k].optional, calling_var=optional_calling_var)
                                subroutine.arguments[k] = new_tuple
                        else:
                            new_tuple = var_metadata_type(longname=subroutine.arguments[k].longname, units=subroutine.arguments[k].units, id=subroutine.arguments[k].id, rank=subroutine.arguments[k].rank, type=subroutine.arguments[k].type, description=subroutine.arguments[k].description, kind=subroutine.arguments[k].kind, intent=subroutine.arguments[k].intent, optional=subroutine.arguments[k].optional, calling_var=subroutine.calling_vars[k])
                            subroutine.arguments[k] = new_tuple


calling_var_set = set()
for scheme in schemes:
    for subroutine in scheme.subroutines:
        for var in subroutine.arguments:
            #only add the calling var to the set if it is not empty
            if(var.calling_var):
                calling_var_set.add(var.calling_var)

longname_conflicts = []
longname_success = []

for calling_var in sorted(calling_var_set):
    #process each calling variable in the set by searching through the schemes / subroutines for where the calling variable is used, saving the calling var, longname, local_name, and subroutine_name for each time a calling variable is used.

    calling_vars = []
    longnames = []
    local_names = []
    subroutine_names = []
    for scheme in schemes:
        for subroutine in scheme.subroutines:
            for var in subroutine.arguments:
                if var.calling_var == calling_var:
                    calling_vars.append(calling_var)
                    longnames.append(var.longname)
                    local_names.append(var.id)
                    subroutine_names.append(subroutine.name)

    #check for conflicts; a conflict is when not all longnames used for each calling variable match exactly
    if longnames.count(longnames[0]) == len(longnames):
        longname_success.append((calling_vars, longnames, local_names, subroutine_names))
    else:
        longname_conflicts.append((calling_vars, longnames, local_names, subroutine_names))

    #print the list of all calling variables and where they are being used
    print calling_var, subroutine_names

#print the conflicts (or success)
if len(longname_success) == len(calling_var_set):
    print "100% success!"
else:
    print str(len(longname_conflicts)) + ' conflicts were found out of ' + str(len(calling_var_set)) + ' possible comparisons.'
    print 'Conflicts:'
    for conflict in longname_conflicts:
        for i in range(len(conflict[0])):
            print conflict[0][i], conflict[1][i], conflict[2][i], conflict[3][i]
        print #blank line
