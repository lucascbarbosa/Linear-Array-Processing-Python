def interp2(x,y,z, xi, yi):
    '''This function implements cubic interpolation without splines as described in:
        Cubic convolution interpolation for digital image processing.  Robert Keys.
        IEEE transactions on acoustics, speech, and signal processing.  Vol. 29. No. 6. 1981.'''

    ##TODO change from matlab indexing##

    import numpy as np
    
    rows, cols = z.shape
    mx = len(x)
    my = len(y)

    #Normalize the units on the requested positions to the given positions
    s = 1 + (xi - x[0])/(x[-1] - x[0])*(cols - 1)
    t = 1 + (yi - y[0])/(y[-1] - y[0])*(rows - 1)

    if np.any(t < 1) or np.any( s< 1) or np.any(t > rows) or np.any(s > cols):
        print 'xi or yi is out of bounds'
        import sys
        sys.exit()

    #2-D array element indexing, adjusted for boundary padding
    ndx = (t).astype('int') + (s - 1).astype('int')*(rows + 2)

    # Check for out of range values of s and set to 1
    s[(s<1) or (s>cols)] = 1

    # Check for out of range values of t and set to 1
    s[(t<1) or (s>rows)] = 1
    
    #check for boundary values
    d = s==cols
    s = s - s.astype('int')
    s[d] = s[d] + 1.
    ndx[d] = ndx[d] - rows - 2
    
    #check for boundary values
    d = t==rows
    t = t - t.astype('int')
    t[d] = t[d] + 1.
    ndx[d] = ndx[d] - rows - 1

    #Expand z so interpolation is valid at the boundaries.
    zz = np.zeros( (z.shape[0]+2, z.shape[0]+2) )
    zz[1:rows+1,1:cols+1] = z;
    
    zz[0,1:cols+1] = 3*z[0,:]-3*z[1,:]+z[2,:];
    zz[rows+1,1:cols+1] = 3*z[rows-1,:]-3*z[rows-2,:]+z[rows-3,:];
    
    zz[:,0] = 3*zz[:,1]-3*zz[:,2]+zz[:,3];
    zz[:,cols+1] = 3*zz[:,cols]-3*zz[:,cols-1]+zz[:,cols-2];    
    
    rows += 2 

    # Now interpolate using computationally efficient algorithm.
    t0 = -t**3 + 2*t**2 -t
    t1 = 3*t**3 - 5*t**2 +2
    t2 = -3*t**3 + 4*t**2 +t
    t = t**3-t**2

    #Changes for compatability with numpy   
    flatZZ = zz.T.flatten()
    ndx -= 1    

    F= ( flatZZ[ndx]*t0 + flatZZ[ndx+1]*t1 + flatZZ[ndx+2]*t2 + flatZZ[ndx+3]*t )* (-s**3 + 2*s**2 - s)
    
    ndx +=  rows;
    F  +=  ( flatZZ[ndx]*t0 + flatZZ[ndx+1]*t1 + flatZZ[ndx+2]*t2 + flatZZ[ndx+3]*t ) * (3*s**3 - 5*s**2 + 2)
        
    ndx += rows;
    F  +=  ( flatZZ[ndx]*t0 + flatZZ[ndx+1]*t1 + flatZZ[ndx+2]*t2 + flatZZ[ndx+3]*t ) * (-3*s**3 + 4*s**2 + s)
            
    ndx += rows;
    F  +=  ( flatZZ[ndx]*t0 + flatZZ[ndx+1]*t1 + flatZZ[ndx+2]*t2 + flatZZ[ndx+3]*t ) * (s**3 - s**2)
            
    F /= 4;

    return F
