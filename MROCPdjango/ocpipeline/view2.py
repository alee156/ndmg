'''
@author : Disa Mhembere
Module to hold the views of a Django one-click MR-connectome pipeline
'''
import os, sys, re

from django.shortcuts import render_to_response
from django.shortcuts import render
from django.template import RequestContext
from django.http import HttpResponseRedirect

from django.core.files import File        # For programmatic file upload

from ocpipeline.models import Document
from ocpipeline.models import TrialDoc
from ocpipeline.forms import DocumentForm
from ocpipeline.forms import OKForm
from ocpipeline.forms import DataForm
from ocpipeline.forms import TestForm
import mrpaths

#import django
import zipfile
import tempfile

from django.http import HttpResponse
from django.http import HttpResponseBadRequest

''' Data Processing imports'''
from mrcap import gengraph as gengraph

import ocpipeline.filesorter as filesorter
import ocpipeline.zipper as zipper
import ocpipeline.createDirStruct as createDirStruct
import ocpipeline.convertTo as convertTo

from django.core.servers.basehttp import FileWrapper
from django.conf import settings

import subprocess
from shutil import move, rmtree # For moving files

'''
Global Paths
'''
uploadDirPath = '/data/projects/disa/OCPprojects/' # Global path to files that are uploaded by users
processingScriptDirPath = os.path.abspath(os.path.curdir) + "/ocpipeline/mrcap/" # Global path to location of processing code

'''
Global file Names all initialized to an empty string
'''
roi_xml_fn = ''
fiber_fn = ''
roi_raw_fn = ''

''' To hold each type of file available for download'''
derivatives = ''    # _fiber.dat, _roi.xml, _roi.raw
rawdata = ''        # none yet
graphs = ''         # biggraph, smallgraph
graphInvariants = ''# lcc.npy (largest connected components), svd.ny (Single Value Decomposition)
images = ''	    # To hold images  

userDefProjectDir = '' # To be defined by user
scanId = '' # To be defined by user

urlBit = False # This bit will be set if user decides to proceed using url version

smGrfn_gl = ''
bgGrfn_gl = ''
lccfn_gl = ''
SVDfn_gl = ''

''' Little welcome message'''
def default(request):
    return render_to_response('welcome.html')

def createProj(request, webargs=None):
    global userDefProjectDir
    global scanId
    global uploadDirPath
    
    ''' Browser url version''' 
    if (webargs):
        [userDefProjectName, site, subject, session, scanId] = request.path.split('/')[2:7] # This will always be true
    
        userDefProjectName = os.path.join(uploadDirPath, userDefProjectName) # Fully qualify
        userDefProjectDir =  os.path.join(userDefProjectName, site, subject, session, scanId)
	
        return HttpResponseRedirect(settings.BASE_URL+'/pipelineUpload') # Redirect after POST
    
    ''' Form '''
    if request.method == 'POST':
        form = DataForm(request.POST)
        if form.is_valid():
            userDefProjectName = form.cleaned_data['UserDefprojectName']
            site = form.cleaned_data['site']
            subject = form.cleaned_data['subject']
            session = form.cleaned_data['session']
            scanId = form.cleaned_data['scanId']
        
	    userDefProjectName = os.path.join(uploadDirPath, userDefProjectName) # Fully qualify
	    userDefProjectDir =  os.path.join(userDefProjectName, site, subject, session, scanId)
	    ###userDefProjectDir ='/data/projects/disa/OCPprojects/Test1/Site/Name/Session/Scan'

        return HttpResponseRedirect(settings.BASE_URL+'/pipelineUpload') # Redirect after POST
    else:
        form = DataForm() # An unbound form
   
    return render(request, 'nameProject.html', {
        'form': form,
    })

''' Successful completion of task'''
def success(request):
    return render_to_response('success.html')   






def pipelineUpload(request, webargs=None):
    global userDefProjectDir
    global derivatives
    global rawdata
    global graphs
    global graphInvariants
    global images
    
    ''' Form '''
    if request.method == 'POST':
        form = TestForm(request.POST, request.FILES) # instantiating form
        if form.is_valid():
	    
	    ''' Define data directory paths '''
	    derivatives, rawdata,  graphs, graphInvariants, images = defDataDirs(userDefProjectDir)
	    
            newdoc = TrialDoc(docfile = request.FILES['docfile'])
	    newdoc._meta.get_field('docfile').upload_to = '/data/projects/disa/OCPprojects/STATtest/jhsdgk/gdagsdg/dgsdgg' # route files to correct location
            print '\nSaving all files complete...'
            newdoc.save()
        return HttpResponseRedirect('disa'+'/success')
    else:
        form = TestForm() # An empty, unbound form
        
    # Render the form
    return render_to_response(
        'singtrial.html',
        {'form': form},
        context_instance=RequestContext(request) # Some failure to input data & returns a key signaling what is requested
    )





def processInputData(request):
    '''
    Extract File Name
    Determine what file corresponds to what for gengraph
    '''
    global roi_xml_fn
    global fiber_fn
    global roi_raw_fn
    global derivatives
    global urlBit
    
    filesInUploadDir = os.listdir(derivatives)
    
    roi_xml_fn, fiber_fn, roi_raw_fn = filesorter.checkFileExtGengraph(filesInUploadDir) # Check & sort files
    
    for fileName in [roi_xml_fn, fiber_fn, roi_raw_fn]:
	if fileName == "": # Means a file is missing from i/p
	    return render_to_response('pipelineUpload.html', {'form': form}, context_instance=RequestContext(request)) # Missing file for processing Gengraph    
    
    baseName = fiber_fn[:-9] #MAY HAVE TO CHANGE
    
    ''' Fully qualify file names''' 
    fiber_fn = os.path.join(derivatives, fiber_fn)
    roi_raw_fn = os.path.join(derivatives, roi_raw_fn)
    roi_xml_fn = os.path.join(derivatives, roi_xml_fn)
    
    
    global graphs  # let function see path for final graph residence
    global processingScriptDirPath
    global graphInvariants
    
    global smGrfn_gl
    global bgGrfn_gl
    global lccfn_gl
    global SVDfn_gl
    
    [ smGrfn_gl, bgGrfn_gl, lccfn_gl, SVDfn_gl ] \
	= processData(fiber_fn, roi_xml_fn, roi_raw_fn,graphs, graphInvariants, True)

    if (urlBit):
	return HttpResponseRedirect(settings.BASE_URL+'/zipOutput')

    return HttpResponseRedirect(settings.BASE_URL+'/confirmDownload')


def confirmDownload(request):
    
    global smGrfn_gl
    global bgGrfn_gl
    global lccfn_gl
    global SVDfn_gl
    
    if 'zipDwnld' in request.POST: # If zipDwnl option is chosen
	form = OKForm(request.POST)
	return HttpResponseRedirect(settings.BASE_URL+'/zipOutput') # Redirect after POST
    
    elif 'convToMatNzip' in request.POST: # If view dir structure option is chosen
	form = OKForm(request.POST)
	convertTo.convertLCCtoMat(lccfn_gl)
	convertTo.convertSVDtoMat(SVDfn_gl)
	# Incomplete
	#convertTo.convertGraphToCSV(smGrfn_gl)
	#convertTo.convertGraphToCSV(bgGrfn_gl)
	return HttpResponseRedirect(settings.BASE_URL+'/zipOutput')
    
    elif 'getProdByDir' in request.POST: # If view dir structure option is chosen
	form = OKForm(request.POST)
	return HttpResponseRedirect('http://www.openconnecto.me' + userDefProjectDir)
    
    elif 'convToMatNgetByDir' in request.POST: # If view dir structure option is chosen
	form = OKForm(request.POST)
	convertTo.convertLCCtoMat(lccfn_gl)
	convertTo.convertSVDtoMat(SVDfn_gl)
	# Incomplete
	#convertTo.convertGraphToCSV(smGrfn_gl)
	#convertTo.convertGraphToCSV(bgGrfn_gl)
	return HttpResponseRedirect('http://www.openconnecto.me' + userDefProjectDir)
    
    else:
	form = OKForm()
    return render(request, 'confirmDownload.html', {
        'form': form,
    })


def zipProcessedData(request):
    '''
    Compress data products to single zip for upload
    '''
    print '\nBeginning file compression...'
    # Take dir with multiple scans, compress it & send it off 
    
    global scanId
    global userDefProjectDir
    
    ''' Zip it '''
    temp = zipper.zipFilesFromFolders(dirName = userDefProjectDir)
    ''' Wrap it '''
    wrapper = FileWrapper(temp) 
    response = HttpResponse(wrapper, content_type='application/zip')
    response['Content-Disposition'] = ('attachment; filename='+ scanId +'.zip')
    response['Content-Length'] = temp.tell()
    temp.seek(0)
    ''' Send it '''
    return response

def upload(request, webargs=None):
    global uploadDirPath
    """Programmatic interface for uploading data"""  
    if (webargs and request.method == 'POST'):
	
	[userDefProjectName, site, subject, session, scanId, addmatNcsv] = webargs.split('/') # [:-1] # Add to server version
	
	userDefProjectDir = os.path.join(uploadDirPath, userDefProjectName, site, subject, session, scanId)
	
	''' Define data directory paths '''
	derivatives, rawdata,  graphs, graphInvariants, images = defDataDirs(userDefProjectDir)
	
	''' Make appropriate dirs if they dont already exist '''    
	createDirStruct.createDirStruct([derivatives, rawdata, graphs, graphInvariants, images])
	print 'Directory structure created...'
	
	''' Get data from request.body '''
	
	tmpfile = tempfile.NamedTemporaryFile()
	tmpfile.write ( request.body )
	tmpfile.flush()
	tmpfile.seek(0)
	rzfile = zipfile.ZipFile ( tmpfile.name, "r" )
	
	print 'Temporary file created...'
	
	''' Extract & save zipped files '''
	uploadFiles = []
	for name in (rzfile.namelist()):	
	    outfile = open(os.path.join(derivatives, name.split('/')[-1]), 'wb') # strip name of source folders if in file name
	    outfile.write(rzfile.read(name))
	    outfile.flush()
	    outfile.close()
	    uploadFiles.append(os.path.join(derivatives, name.split('/')[-1])) # add to list of files
	    print name + " written to disk.."
	
	  # Check which file is which
	roi_xml_fn, fiber_fn, roi_raw_fn = filesorter.checkFileExtGengraph(uploadFiles) # Check & sort files
	
	''' Data Processing '''
	[ smGrfn, bgGrfn, lccfn, SVDfn ] \
	  = processData(fiber_fn, roi_xml_fn, roi_raw_fn,graphs, graphInvariants, True) # Change to false to not process anything
	
	''' If optional .mat graph invariants & .csv graphs '''
	if re.match(re.compile('(y|yes)$',re.I),addmatNcsv):
	    convertTo.convertLCCtoMat(lccfn)
	    convertTo.convertSVDtoMat(SVDfn)
		# Incomplete
	    #convertTo.convertGraphToCSV(smGrfn)
	    #convertTo.convertGraphToCSV(bgGrfn)
	    
	#ret = rzfile.printdir()
	#ret = rzfile.testzip()
	#ret = rzfile.namelist()
	
	dwnldLoc = "http://www.openconnecto.me/data/projects/disa/OCPproject/"+ webargs
	return HttpResponse ( "Files available for download at " + dwnldLoc) # change to render of a page with a link to data result
    
    elif(not webargs):
	return django.http.HttpResponseBadRequest ("Expected web arguments to direct project correctly")
  
    else:
	return django.http.HttpResponseBadRequest ("Expected POST data, but none given")

'''********************* Standalone Methods  *********************'''

def getFiberPath(fiberFileName):
    '''
    fiberFileName - is a tract file name with naming convention '[filename]_fiber.dat'
	where filename may vary but _fiber.dat may not.
    This returns fiberfn's full path less the 'fiber.dat' portion
    '''
    return fiberFileName.partition('_')[0]

def defDataDirs(projectDir):
    '''
    Define all the paths to the data product directories
    projectDir - the fully qualified path of the project directory
    '''
    derivatives = os.path.join(projectDir, 'derivatives')
    rawdata = os.path.join(projectDir, 'rawdata')
    graphs = os.path.join(projectDir, 'graphs')
    graphInvariants = os.path.join(projectDir, 'graphInvariants')
    images = os.path.join(projectDir, 'images')
    
    return [derivatives, rawdata, graphs, graphInvariants, images]

def getFiberID(fiberfn):
    '''
    Assumptions about the data made here as far as file naming conventions
    fiberfn - the dMRI streamline file in format {filename}_fiber.dat
    '''
    if fiberfn.endswith('/'):
	fiberfn = fiberfn[:-1] # get rid of trailing slash
    return fiberfn.split('/')[-1][:-9]

def processData(fiber_fn, roi_xml_fn, roi_raw_fn,graphs, graphInvariants, run = False):
    '''
    graphs - Dir where biggraphs & smallgraphs are saved
    graphInvariants - Dir where graph invariants are saved
    run - Default is false so nothing is actually run
    '''
    if (run):
	import mrcap.svd as svd
	import mrcap.lcc as lcc
	
	baseName = getFiberID(fiber_fn) #VERY TEMPORARY
		
	'''Run gengraph SMALL & save output'''
	print("Running Small gengraph....")
	smGrfn = os.path.join(graphs, (baseName +'smgr.mat'))
	''' spawn subprocess to create small since its result is not necessary for processing '''
	#arguments = 'python ' + '/home/disa/MR-connectome/mrcap/gengraph.py /home/disa' + fiber_fn + ' /home/disa' + smallGraphOutputFileName +' /home/disa' + roi_xml_fn + ' /home/disa' + roi_raw_fn
	#arguments = 'python ' + '/Users/dmhembere44/MR-connectome/mrcap/gengraph.py /Users/dmhembere44' + fiber_fn + ' /Users/dmhembere44' + smallGraphOutputFileName + ' roixmlname=/Users/dmhembere44' + roi_xml_fn + ' roirawname=/Users/dmhembere44' + roi_raw_fn
	#subprocess.Popen(arguments,shell=True)
	gengraph.genGraph(fiber_fn, smGrfn, roi_xml_fn, roi_raw_fn)
	
	''' Run gengrah BIG & save output '''
	print("\nRunning Big gengraph....")
	bgGrfn = os.path.join(graphs, (baseName +'bggr.mat')) 
	#**gengraph.genGraph(fiber_fn, bgGrfn, roi_xml_fn ,roi_raw_fn, True)
	
	''' Run LCC '''
	lccfn = os.path.join(graphInvariants, (baseName + 'lcc.npy'))
	
	'''Should be big but we'll do small for now'''
	#**lcc.process_single_brain(roi_xml_fn, roi_raw_fn, bgGrfn, lccfn)
	lcc.process_single_brain(roi_xml_fn, roi_raw_fn, smGrfn, lccfn)
	
	''' Run Embed - SVD '''
	SVDfn = os.path.join(graphInvariants, (baseName + 'svd.npy'))
	
	print("Running SVD....")
	
	roiBasename = str(roi_xml_fn[:-4]) # WILL NEED ADAPTATION
	#**svd.embed_graph(lccfn, roiBasename, bgGrfn, SVDfn)
	svd.embed_graph(lccfn, roiBasename, smGrfn, SVDfn)
	return [ smGrfn, bgGrfn, lccfn, SVDfn ] 
    else:
	print 'Theoretically I just ran some processing...'
	return [ '','','','' ] 