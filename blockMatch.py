#first define the class unique priority queue
from Queue import PriorityQueue
import heapq
from rfData import rfClass
import cv
import numpy as np
from matplotlib import pyplot as plt
from scipy.signal import hilbert

class UniquePriorityQueue(PriorityQueue):
    def _init(self, maxsize):
        '''This is meant to take in tuples of
        (-quality, locInd, iniDpY, iniDpX, region)'''
        PriorityQueue._init(self, maxsize)
        self.locations = []
        self.itemsInQueue = []

    def _put(self, item, heappush=heapq.heappush):
        #unique items added to list without checks
        if item[1] not in self.locations:
            self.locations.append(item[1])
            self.itemsInQueue.append(item)
            PriorityQueue._put(self, item, heappush)

        #if already in list, then only insert if
        #quality is higher than what is already in list
        elif item[1] in self.locations:
            if abs(item[0]) < abs( self.itemsInQueue[ self.locations.index(item[1]) ][0] ):
                pass #no insertion, correlation is lower than what is already in list
            else:

                tmpItem = self.itemsInQueue.pop( self.locations.index(item[1]) )
                self.queue.remove( tmpItem )
                self.locations.remove(item[1])

                self.locations.append(item[1])
                self.itemsInQueue.append(item)
                PriorityQueue._put(self, item, heappush)


    def _get(self, heappop=heapq.heappop):
        item = PriorityQueue._get(self, heappop)
        self.itemsInQueue.pop( self.locations.index(item[1]) )
        self.locations.remove(item[1])
        return item


class blockMatchClass(rfClass):


    def __init__(self, fname, dataType, postFile = None,  selectRoi = False,windowYmm = 1.0, windowXmm = 4.0, rangeYmm = 1.0, rangeXmm = .6, overlap = .65,
    strainKernelmm = 6.0):
        '''Input:
        fname: (string)  Either a file containing a sequence of frames with motion, or a pre-compression file.
        dataType: (string)  The filetype of the input files, see rfClass for allowed types
        postFile: (string)  A file of post compression data, the same type and dimensions as the input file
        windowYmm: (float) the axial window size of the block match window in mm
        windowXmm: (float)  The lateral window size of the block match window in mm
        rangeYmm:  (float)  The axial search range for the block match window in mm
        rangeXmm:  (float)  The lateral search range for the block match window in mm
        overlap:  (float)  [0-1].  The axial overlap between block matching windows.
        strainKernelmm:  (float)  The size of the least squares strain estimation kernel in mm.

        '''
        super(blockMatchClass, self).__init__(fname, dataType)

        if postFile:
            self.postRf = rfClass(postFile, dataType)
        else:
            self.postRf = None
        self.windowYmm = windowYmm
        self.windowXmm = windowXmm
        self.rangeYmm =  rangeYmm
        self.rangeXmm = rangeXmm

        #axial block size
        self.windowY = int(self.windowYmm/self.deltaY)
        if not self.windowY%2:
            self.windowY += 1
        self.halfY = self.windowY//2

        #lateral block size
        if self.imageType == 'la':
            self.windowX = int(self.windowXmm/self.deltaX)
        else:
            self.windowX = 21
        if not self.windowX%2:
            self.windowX +=1
        self.halfX = self.windowX//2


        #search range
        if self.imageType == 'la':
            self.rangeX = int(self.rangeXmm/self.deltaX)
        else:
            self.rangeX = 10
        self.rangeY = int(self.rangeYmm/self.deltaY)
        self.smallRangeY = 3
        self.smallRangeX = 2

        #overlap and step
        self.overlap = overlap
        self.stepY =int( (1 - self.overlap)*self.windowY )


        ####work out tracking boundaries
        self.startY = 0 + self.rangeY + self.smallRangeY + self.halfY
        self.stopY = self.points - self.halfY - self.smallRangeY - self.rangeY #last pixel that can fit a window

        self.startX = 0 + self.halfX + self.rangeX + self.smallRangeX
        self.stopX = self.lines - self.halfX - self.smallRangeX - self.rangeX
        
        ###Allow for selection of an ROI####
        if self.imageType == 'la' and selectRoi:
            self.SetRoiBoxSelect()
                
            if self.roiX[0] > self.startX:
                self.startX = self.roiX[0]

            if self.roiX[1] < self.stopX:
                self.stopX = self.roiX[1]
            
            if self.roiY[0] > self.startY:
                self.startY = self.roiY[0]

            if self.roiY[1] < self.stopY:
                self.stopY = self.roiY[1]

        
        ###Re-adjust roiX, roiY for display
        self.roiY = [self.startY, self.stopY]
        self.roiX = [self.startX, self.stopX]

        if selectRoi and self.imageType == 'la':
            self.ShowRoiImage()

    ###create arrays containing window centers in rf data coordinates
        self.windowCenterY = range(self.startY,self.stopY, self.stepY)
        self.numY = len(self.windowCenterY)

        self.windowCenterX = range(self.startX,self.stopX)
        self.numX = len(self.windowCenterX)


    #work out strainwindow in rf pixels, divide by step to convert to displacement pixels
    #make odd number
        self.strainWindow = int(strainKernelmm/(self.deltaY*self.stepY) )
        if not self.strainWindow%2:
            self.strainWindow += 1
        self.halfLsq = self.strainWindow//2
        self.strainwindowmm = self.strainWindow*self.deltaY*self.stepY
       
        if self.numY - 1 < self.strainWindow or self.numX < 1:
            print "ROI is too small"
            import sys
            sys.exit()

    def WriteParameterFile(self, fname):
        'Write the block matching parameters to file'
        f = open(fname, 'w')
        f.write('Axial window length: ' + str(self.windowYmm) + ' mm. \n')
        f.write('Lateral window length: ' + str(self.windowXmm) + ' mm. \n')
        f.write('Axial search range: ' + str(self.rangeYmm) + ' mm. \n')
        f.write('Lateral search range: ' + str(self.rangeXmm) + ' mm. \n')
        f.write('Ovlerlap: ' + str(self.overlap) + '\n' )


    def InitializeArrays(self):
        '''Called to clear out displacement and quality arrays if
        I'm looking at a sequence of strain images.'''

    ######allocate numpy arrays to store quality, dpy, dpx
        self.dpY = np.zeros( (self.numY, self.numX) )
        self.dpX = np.zeros( (self.numY, self.numX) )
        self.quality = np.zeros( (self.numY, self.numX) )
        self.processed = np.zeros( (self.numY, self.numX) )
        self.regionImage = np.zeros( (self.numY, self.numX) )


    ####seed is tuple containing (quality, ptidx, region)
        self.seedList = UniquePriorityQueue()

    #work out number of seed points, and index into dp arrays
        seedsY = int(.05*self.numY)
        if seedsY == 0:
            seedsY = 1
        seedsX = int(.05*self.numX)
        if seedsX == 0:
            seedsX = 1
        strideY = self.numY/seedsY
        strideX = self.numX/seedsX
        self.seedsY = range(0,self.numY, strideY)
        self.seedsX = range(0,self.numX, strideX)
    #regionarray to determine how many points grown from a particular seed
        self.numRegions = len(self.seedsY)*len(self.seedsX)
        self.regionArray = np.ones( self.numRegions )

    #for determining bad seeds
        self.threshold = round( (self.numY/10)*(self.numX/10) )

    def CreateStrainImage(self, preFrame = 0, skipFrame = 0, vMax = None, pngFileName = None, itkFileName = None):
        '''With the given parameters, pre, and post RF data create a strain image.'''

        #get pre and post frame
        self.ReadFrame(preFrame)
        self.pre = self.data.copy()

        if self.postRf:
            self.postRf.ReadFrame(preFrame)
            self.post = self.postRf.data.copy()
        else:
            self.ReadFrame(preFrame + 1 + skipFrame)
            self.post = self.data.copy()

        self.InitializeArrays()

        #Perform tracking
        self.TrackSeeds()
        self.TrackNonSeeds()
        #self.DropOutCorrection()
        self.DisplacementToStrain()
        
        if vMax:
            self.strain[self.strain> vMax] = vMax

        #take the strain image and create a scan-converted strain image.
        startY =self.windowCenterY[self.halfLsq]
        startYdp = self.windowCenterY[0]
        startX =self.windowCenterX[0]
        stepY =self.stepY
        stepX =1

        #Write image to itk format
        if itkFileName:

            import SimpleITK as sitk 
            
            #First strain
            itkIm = sitk.GetImageFromArray(self.strain)

            halfWind = int( (self.strainWindow-1)/2 )
            itkIm.SetSpacing( [self.deltaY*stepY, self.deltaX*stepX] )
            itkIm.SetOrigin( [(startY + halfWind)*self.deltaY, startX*self.deltaX] )
            
            writer = sitk.ImageFileWriter()
            if itkFileName[-4:] != '.mhd':
                itkFileName += '.mhd'
            writer.SetFileName(itkFileName)
            
            writer.Execute(itkIm)
            
            #dpY
            itkIm = sitk.GetImageFromArray(self.dpY)

            itkIm.SetSpacing( [self.deltaY*stepY, self.deltaX*stepX] )
            itkIm.SetOrigin( [startY*self.deltaY, startX*self.deltaX] )
            
            writer.SetFileName(itkFileName[:-4] + 'dispY.mhd')
            writer.Execute(itkIm)

            #dpX
            itkIm = sitk.GetImageFromArray(self.dpX)

            itkIm.SetSpacing( [self.deltaY*stepY, self.deltaX*stepX] )
            itkIm.SetOrigin( [startY*self.deltaY, startX*self.deltaX] )
            
            writer.SetFileName(itkFileName[:-4] + 'dispX.mhd')
            writer.Execute(itkIm)

       
        ##Write image to PNG
        
        self.strainRGB = self.CreateParametricImage(self.strain,[startY, startX], [stepY, stepX], colormap = 'gray' )
        self.dpYRGB = self.CreateParametricImage(self.dpY,[startYdp, startX], [stepY, stepX] )
        self.dpXRGB = self.CreateParametricImage(self.dpX,[startYdp, startX], [stepY, stepX])
        self.qualityRGB = self.CreateParametricImage(self.quality,[startYdp, startX], [stepY, stepX] )

        if pngFileName:
            
            if pngFileName[-4:] != '.png':
                pngFileName += '.png'
            from matplotlib import pyplot
            pyplot.imshow(self.strainRGB, extent = [0, self.fovX, self.fovY, 0], vmax = self.strain.max(), vmin = 0,
            cmap = 'gray')
            pyplot.colorbar()
            pyplot.savefig(pngFileName)
            pyplot.close()

    def RescaleRgbStrainImage(self, vMax):
        """This function rescales my scan-converted RGB strain image"""
        if self.strain is None:
            print 'Error, no strain image has been calculated yet.'
            return

        startY =self.windowCenterY[self.halfLsq]
        startYdp = self.windowCenterY[0]
        startX =self.windowCenterX[0]
        stepY =self.stepY
        stepX =1
      
        
        tmpStrain = self.strain.copy()
        locs = tmpStrain > vMax
        tmpStrain[locs] = vMax
        self.strainRGB = self.CreateParametricImage(tmpStrain,[startY, startX], [stepY, stepX], colormap = 'gray' )

    def DisplayScanConvertedStrainImage(self, vMax = .02):

        bmode = np.log10(abs(hilbert(self.data) ) )
        bmode -= bmode.max()

        if self.imageType == 'la':
            fig = plt.figure()
            fig.canvas.set_window_title("B-mode image " )
            ax = fig.add_subplot(1,1,1)
            ax.imshow(self.strainRGB, extent = [0, self.fovX, self.fovY, 0] )
            ax.show()
        
        if self.imageType == 'ps':

            plt.pcolormesh(self.X,self.Y, bmode,hold = True, vmin = -3, vmax = 0, cmap = 'gray')
            tmpX = np.zeros(self.strain.shape)
            tmpY = np.zeros(self.strain.shape)
            strainYrf = self.windowCenterY[self.halfLsq:-self.halfLsq]
            for i in range(tmpX.shape[0]):
                for j in range(tmpY.shape[1]):
                    tmpX[i,j] = self.X[strainYrf[i], self.windowCenterX[j] ]
                    tmpY[i,j] = self.Y[strainYrf[i], self.windowCenterX[j] ]
           
            print tmpX.shape
            print tmpY.shape
            plt.pcolormesh(tmpX,tmpY, self.strain, vmin = 0, vmax = vMax, cmap = 'gray')
            plt.gca().set_axis_bgcolor("k")
            plt.ylim(plt.ylim()[::-1])
            plt.show() 
    
    def SubSampleFit(self,f):
        """This function takes a 3 by 1 array assumes a quadratic function and finds the maximum as if the function were continuous.
The assumption is that f(x) = ax^2 + bx + c"""

        c = f[1]
        a =  (f[0] + f[2] )/2. - c
        b = -(f[0] - f[2] )/2.
        delta = -b/(2*a)
        if abs(delta) > 1:
            delta = 0

        return delta

    def AddToSeedList(self,maxCC, y,x, intDpY,intDpX, region ):
        """Add up to four neighbors to a point to the seed list.  Perform bounds checking to make sure the neighbors aren't
        located out of the image.  Notice that the Normalized cross-correlation goes in as the quality metric, and that the
        sign will be reversed inside the function as necessary. """
    

        Sub2ind = lambda shape, row, col : shape[1]*row + col

        #add point above
        if y > 0 and not self.processed[y-1,x]:
            self.seedList.put( (-maxCC, Sub2ind(self.dpY.shape, y-1, x), intDpY,intDpX, region))


        #add point below
        if y < self.numY - 1 and not self.processed[y+1,x]:
            self.seedList.put((-maxCC, Sub2ind(self.dpY.shape, y+1, x), intDpY,intDpX,region) )

        #add point to left
        if x > 0 and not self.processed[y,x-1]:

            self.seedList.put( (-maxCC, Sub2ind(self.dpY.shape, y, x-1),intDpY,intDpX,region) )

        #add point to right
        if x < self.numX - 1 and not self.processed[y, x+1]:

            self.seedList.put( (-maxCC, Sub2ind(self.dpY.shape, y, x+1),intDpY,intDpX,region) )



    def TrackSeeds(self):
        """Perform block-matching only on the seed points """
    #allocate array to hold results of cross correlation
        resultNp = np.float32( np.zeros( (2*self.rangeY + 1, 2*self.rangeX + 1) ) )
        resultCv = cv.fromarray(resultNp)


        region = 0

    #perform tracking on seed points
        for y in self.seedsY:
            for x in self.seedsX:

                self.processed[y,x] = True
                self.regionImage[y,x] = region

                #GRAB SLICE OF DATA FOR CC CONVERT TO CV FRIENDLY FORMAT
                startBlockY = self.windowCenterY[y] - self.halfY
                stopBlockY = self.windowCenterY[y] + self.halfY + 1
                startBlockX = self.windowCenterX[x] - self.halfX
                stopBlockX = self.windowCenterX[x] + self.halfX + 1
                template = cv.fromarray( np.float32(self.pre[startBlockY:stopBlockY, startBlockX:stopBlockX ] )  )

                startBlockY = self.windowCenterY[y] - self.halfY - self.rangeY
                stopBlockY = self.windowCenterY[y] + self.halfY + 1 + self.rangeY
                startBlockX = self.windowCenterX[x] - self.halfX - self.rangeX
                stopBlockX = self.windowCenterX[x] + self.halfX + 1 + self.rangeX
                image = cv.fromarray( np.float32( self.post[startBlockY:stopBlockY, startBlockX:stopBlockX]  )   )

                cv.MatchTemplate(template, image, resultCv, cv.CV_TM_CCORR_NORMED )
                resultNp = np.asarray(resultCv)


                #FIND MAXIMUM, PERFORM SUB-SAMPLE FITTING
                maxInd = resultNp.argmax()
                maxCC = resultNp.max()
                maxY, maxX = np.unravel_index(maxInd, resultNp.shape)
                self.quality[y,x] = maxCC

                #perform sub-sample fit
                if maxY > 0 and maxY < 2*self.rangeY - 1:
                    deltaY = self.SubSampleFit(resultNp[maxY-1:maxY+2, maxX])
                else:
                    deltaY = 0.0


                if maxX > 0 and maxX < 2*self.rangeX - 1:
                    deltaX = self.SubSampleFit(resultNp[maxY, maxX-1:maxX + 2] )
                else:
                    deltaX = 0.0


                self.dpY[y,x] = maxY - self.rangeY + deltaY
                self.dpX[y,x] = maxX - self.rangeX + deltaX

                intDpY = int(round(self.dpY[y,x]))
                intDpX = int(round(self.dpX[y,x]))

                #PUT ITEM IN SEED LIST
                self.AddToSeedList(maxCC, y,x, intDpY,intDpX, region)

                region +=1


    def TrackNonSeeds(self):
        """Perform block-matching on all the non-seed points, using a very small search range. """

    #re-allocate array to hold results of cross correlation
        resultNp = np.float32( np.zeros( (2*self.smallRangeY + 1, 2*self.smallRangeX + 1) ) )
        resultCv = cv.fromarray(resultNp)



    #perform tracking on other points
        while self.seedList.qsize() > 0:

            (tempQuality, pointInd, iniDpY, iniDpX, region) = self.seedList.get()
            self.regionArray[region] += 1
            (y,x) = np.unravel_index(pointInd, self.dpY.shape)
            self.processed[y,x] = True
            self.regionImage[y,x] = region

            #GRAB SLICE OF DATA FOR CC CONVERT TO CV FRIENDLY FORMAT
            startBlockY = self.windowCenterY[y] - self.halfY
            stopBlockY = self.windowCenterY[y] + self.halfY + 1
            startBlockX = self.windowCenterX[x] - self.halfX
            stopBlockX = self.windowCenterX[x] + self.halfX + 1
            template = cv.fromarray( np.float32(self.pre[startBlockY:stopBlockY, startBlockX:stopBlockX ] )  )

            startBlockY = self.windowCenterY[y] - self.halfY - self.smallRangeY + iniDpY
            stopBlockY = self.windowCenterY[y] + self.halfY + self.smallRangeY + 1 + iniDpY
            startBlockX = self.windowCenterX[x] - self.halfX - self.smallRangeX + iniDpX
            stopBlockX = self.windowCenterX[x] + self.halfX + self.smallRangeX + 1 + iniDpX
            image = cv.fromarray( np.float32( self.post[startBlockY:stopBlockY, startBlockX:stopBlockX]  )   )

            cv.MatchTemplate(template, image, resultCv, cv.CV_TM_CCORR_NORMED )
            resultNp = np.asarray(resultCv)


            #FIND MAXIMUM, PERFORM SUB-SAMPLE FITTING
            maxInd = resultNp.argmax()
            maxCC = resultNp.max()
            maxY, maxX = np.unravel_index(maxInd, resultNp.shape)
            self.quality[y,x] = maxCC

            #perform sub-sample fit
            #fit to f(x) = ax^2 + bx + c in both directions
            if maxY > 0 and maxY < 2*self.smallRangeY - 1:
                deltaY = self.SubSampleFit(resultNp[maxY-1:maxY+2, maxX])
            else:
                deltaY = 0.0


            if maxX > 0 and maxX < 2*self.smallRangeX - 1:
                deltaX = self.SubSampleFit(resultNp[maxY, maxX-1:maxX + 2] )
            else:
                deltaX = 0.0

            #Add in y displacement, keep within allowed range
            self.dpY[y,x] = maxY - self.smallRangeY + deltaY + iniDpY
            if self.dpY[y,x] > self.rangeY:
                self.dpY[y,x] = self.rangeY
            if self.dpY[y,x] < -self.rangeY:
                self.dpY[y,x] = -self.rangeY

            #add in x displacement, keep in range
            self.dpX[y,x] = maxX - self.smallRangeX + deltaX + iniDpX
            if self.dpX[y,x] > self.rangeX:
                self.dpX[y,x] = self.rangeX
            if self.dpX[y,x] < -self.rangeX:
                self.dpX[y,x] = -self.rangeX

            intDpY = int(round(self.dpY[y,x]))
            intDpX = int(round(self.dpX[y,x]))

            #PUT ITEM IN SEED LIST
            self.AddToSeedList(maxCC, y, x, intDpY,intDpX, region)



    def DropOutCorrection(self):
        """Re-run the algorithm, but replace the displacements in all the regions not grown from good seeds"""
        self.processed[:] = 0
    #determine bad regions
        goodSeeds = np.zeros( self.numRegions )
        goodSeeds[self.regionArray > self.threshold ] = 1

        region = 0
    #rerun good seed points
        for y in self.seedsY:
            for x in self.seedsX:

                if goodSeeds[region]:
                    self.processed[y,x] = 1

                    intDpY = int(round(self.dpY[y,x]))
                    intDpX = int(round(self.dpX[y,x]))

                    #PUT ITEM IN SEED LIST
                    self.AddToSeedList(self.quality[y,x], y,x, intDpY,intDpX, region)



                region += 1

    #re-allocate array to hold results of cross correlation
        resultNp = np.float32( np.zeros( (2*self.smallRangeY + 1, 2*self.smallRangeX + 1) ) )
        resultCv = cv.fromarray(resultNp)

    #rerun algorithm, if point was grown from good seed maintain it

        while self.seedList.qsize() > 0:

            (tempQuality, pointInd, iniDpY, iniDpX, region) = self.seedList.get()
            (y,x) = np.unravel_index(pointInd, self.dpY.shape)
            self.processed[y,x] = 1

            #Re-process if not originally from a good seed
            if not goodSeeds[ self.regionImage[y,x] ]:
                self.regionImage[y,x] = region

                #GRAB SLICE OF DATA FOR CC CONVERT TO CV FRIENDLY FORMAT
                startBlockY = self.windowCenterY[y] - self.halfY
                stopBlockY = self.windowCenterY[y] + self.halfY + 1
                startBlockX = self.windowCenterX[x] - self.halfX
                stopBlockX = self.windowCenterX[x] + self.halfX + 1
                template = cv.fromarray( np.float32(self.pre[startBlockY:stopBlockY, startBlockX:stopBlockX ] )  )

                startBlockY = self.windowCenterY[y] - self.halfY - self.smallRangeY + iniDpY
                stopBlockY = self.windowCenterY[y] + self.halfY + self.smallRangeY + 1 + iniDpY
                startBlockX = self.windowCenterX[x] - self.halfX - self.smallRangeX + iniDpX
                stopBlockX = self.windowCenterX[x] + self.halfX + self.smallRangeX + 1 + iniDpX
                image = cv.fromarray( np.float32( self.post[startBlockY:stopBlockY, startBlockX:stopBlockX]  )   )

                cv.MatchTemplate(template, image, resultCv, cv.CV_TM_CCORR_NORMED )
                resultNp = np.asarray(resultCv)


                #FIND MAXIMUM, PERFORM SUB-SAMPLE FITTING
                maxInd = resultNp.argmax()
                maxCC = resultNp.max()
                maxY, maxX = np.unravel_index(maxInd, resultNp.shape)
                self.quality[y,x] = maxCC

                #perform sub-sample fit
                #fit to f(x) = ax^2 + bx + c in both directions
                if maxY > 0 and maxY < 2*self.smallRangeY - 1:
                    deltaY = self.SubSampleFit(resultNp[maxY-1:maxY+2, maxX])
                else:
                    deltaY = 0.0


                if maxX > 0 and maxX < 2*self.smallRangeX - 1:
                    deltaX = self.SubSampleFit(resultNp[maxY, maxX-1:maxX + 2] )
                else:
                    deltaX = 0.0


                self.dpY[y,x] = maxY - self.smallRangeY + deltaY + iniDpY
                if self.dpY[y,x] > self.rangeY:
                    self.dpY[y,x] = self.rangeY
                if self.dpY[y,x] < -self.rangeY:
                    self.dpY[y,x] = -self.rangeY

                self.dpX[y,x] = maxX - self.smallRangeX + deltaX + iniDpX
                if self.dpX[y,x] > self.rangeX:
                    self.dpX[y,x] = self.rangeX
                if self.dpX[y,x] < -self.rangeX:
                    self.dpX[y,x] = -self.rangeX

                intDpY = int(round(self.dpY[y,x]))
                intDpX = int(round(self.dpX[y,x]))

                #PUT ITEM IN SEED LIST
                self.AddToSeedList(maxCC, y,x, intDpY,intDpX, region)


            else:

                intDpY = int(round(self.dpY[y,x]))
                intDpX = int(round(self.dpY[y,x]))

                #PUT ITEM IN SEED LIST
                self.AddToSeedList(self.quality[y, x], y,x, intDpY,intDpX, region)


    def DisplacementToStrain(self):
        from numpy import zeros, ones, array
        from numpy.linalg import lstsq
        #want to solve equation y = mx + b for m
        #[x1   1      [m     = [y1
        # x2   1       b ]      y2
        # x3   1]               y3]
        #
        #strain image will be smaller than displacement image

        self.strain = zeros( (self.numY - self.strainWindow + 1, self.numX) )
        A = ones( (self.strainWindow,2) )
        colOne = array( range(0, self.strainWindow) )
        A[:,0] = colOne
        halfWindow = (self.strainWindow-1)/2
        self.startYstrain = self.startY + self.stepY*halfWindow
        self.stopYstrain = self.stopY - self.stepY*halfWindow

        for y in range( halfWindow,self.numY - halfWindow):
            for x in range(self.numX):
                b = self.dpY[y - halfWindow: y + halfWindow + 1, x]
                out = lstsq(A, b)
                xVec = out[0]
                self.strain[y - halfWindow,x] = xVec[0]

        self.strain = self.strain/self.stepY
        self.strain = abs(self.strain)
