# Generate an AR process with mismatched AR coefficients - for training and evaluation of model

from utilities import matSave
import torch

# ARCoeffecientGeneration: Function that returns a matrix that works as an AR processes F matrix
#   Inputs:  (arCoeffMeans, arCoefficientNoiseVar)
#       arCoeffMeans (array) - mean values of the AR coefficients to be generated
#           arCoeffMeans[0] (float) - first AR coefficient
#           arCoeffMeans[1] (float) - second AR coefficient
#       arCoefficientNoiseVar (float) - variance of the AR coefficients to be generated
#   Outputs: (arCoeffMatrix)
#       arCoeffMatrix (tensor [2 x 2]) - the F matrix of an AR process (Bar-Shalom's notation)
#                                                                   
def ARCoeffecientGeneration(arCoeffMeans,arCoeffecientNoiseVar, seed=-1, cuda=False):
    if(seed > 0):
        torch.manual_seed(seed)

    arCoeffsMatrix = torch.eye(2)
    arCoeffsMatrix[1] = arCoeffsMatrix[0]
    goodCoeffs = False
    # Pre-Allocating the arCoeffNoise array
    arCoeffNoise = torch.empty(2,1, dtype=torch.float)
    eigValsEvaluated = torch.empty(2, dtype=torch.float)
    if (cuda):
        arCoeffsMatrix.cuda()
        arCoeffNoise.cuda()
        eigValsEvaluated.cuda()

    while(not goodCoeffs):
        # Generate new AR Coefficients until you get a pair who's eigenvalues are 
        # less than 1.
        # We do this because the system would explode to infinity if the eigenvalues 
        # were greater than 1.
        arCoeffNoise[0] = torch.randn(1) * arCoeffecientNoiseVar
        arCoeffNoise[1] = torch.randn(1) * arCoeffecientNoiseVar
        arCoeffsMatrix[0,0] = arCoeffMeans[0] + arCoeffNoise[0]
        arCoeffsMatrix[0,1] = arCoeffMeans[1] + arCoeffNoise[1]

        # Compute EigenValues of F
        eigValsEvaluated = torch.abs(torch.eig(arCoeffsMatrix, eigenvectors=False).eigenvalues) > 1
        # Determine if any of them have a greater magnitude than 1
        if (not eigValsEvaluated.any()):
            goodCoeffs=True
    return arCoeffsMatrix



# ARDatagenMismatch: Function that returns a set of data with a specified length, that
#                    comes from an AR process with AR coefficients that have some small
#                    amount of noise added to them
#   Inputs: (params, seed)
#       params (list) - a set of parameters to pass to the model
#           params[0] (int) - simLength: amount of batches of data to be generated by the
#                                        simulation
#           params[1] (int) - AR_n: The AR process order (The number of AR coefficients)
#           params[2] (float) - AR_coefficient_noise_var: variance in the AR coefficient from
#                                                         their mean
#           params[3] (int) - batchSize: size of the batches of data we want to generate
#           params[4] (int) - sequenceLength: length of the sequence of data to generate for an
#                             element of a batch
#       seed (int) {default=a random number} - the seed of the random number generator
#                                              for this AR process
#       cuda (Bool) {default=False} - whether to use the GPU and cuda for data generation or not
#   Outputs: (x, z)
#       x (tensor [batchSize x 4  x simuLength]) - a tensor of the real state values of the AR
#                               process separated into batch elements in the 1st dimension,
#                               complex and real state values of the AR process in the 2nd
#                               dimension, and separated by series in the 3rd dimension
#           x[:,0,:] (float) - real value of the current actual state
#           x[:,1,:] (float) - real value of the next actual state
#           x[:,2,:] (float) - imaginary value of the current actual state
#           x[:,3,:] (float) - imaginary value of the next actual state
#
#       z (tensor [batchSize x 2 x sequenceLength x simuLength]) - a tensor of the measured state
#                               values of the AR process separated into batch elements in the 1st
#                               dimension, separated into real and complex numbers in the 2nd
#                               dimension, separated into a sequence of observations in the 3rd
#                               dimension, and separated by series in the 4th dimension
#           z[:,0,:,:] (float) - real values of the measured state
#           z[:,1,:,:] (float) - imaginary values of the measured state

# Vocabulary definitions:
#   Sequence: A set of data generated from the same AR process. Has correlation between elements
#   Batch: A set of data that will be processed in parallel by the model.
#          Each element is a sequence
#   Series: A set of data generated to be processed once by the model. Each element is a batch.
#           This code generates one Series of length: simLength

# Additional Notes about this function:
#   - This function saves all the returned values to a data file, as well as every true state of
#     the data for debugging purposes. It will print the name of the file that it saves the data
#     to when it finishs running. The values that are stored for all the true state values are
#     stored as complex numbers to save formatting time while debugging, because those values
#     will not be used by the neural network this will not effect the model
def ARDatagenMismatch(params, seed=int(torch.abs(torch.floor(100*torch.randn(1)))), cuda=False):
    # Set the seed value for repeatable results
    simLength = params[0]
    AR_n = params[1]
    AR_coeffecient_noise_var = params[2]
    batchSize = params[3]
    sequenceLength = params[4]
    torch.manual_seed(seed)

    # Gain matrix on the previous values
    # TODO: Make the AR coefficient means be a parameter you can pass to the function
    arCoeffMeans = torch.tensor([0.5, 0.4])

    # Noise covariance matrix / noise mean
    Q = torch.tensor([[0.1, 0], [0, 0]])
    QChol = torch.tensor([[torch.sqrt(Q[0,0]), 0],[0, 0]])

    # Observation covariance matrix/ noise mean
    R = torch.tensor([0.1])

    # Pre-allocating the matrix that will store the true values of the predicted and current state
    x = torch.zeros((batchSize, 4, simLength), dtype=torch.float)
    # Pre-allocating the matrix that will store the measured data to be fed into the model
    z = torch.zeros((batchSize, 2, sequenceLength, simLength), dtype=torch.float)

    # Pre-allocating for the system noise vector
    # Matrix format: 1st element is the real part of the noise, 2nd element is the imaginary part of the noise,
    #                1st dimension is current state noise, 2nd dimension is the last state noise (this will always
    #                be 0)
    v = torch.empty(2,2, dtype=torch.float)

    # Pre-allocating for the observation noise vector
    # Matrix format: 1st element is the real part of the noise, 2nd element is the imaginary part of the noise
    w = torch.empty(2, dtype=torch.float)

    # Pre-allocating for the current true state and observed state vectors
    # Matrix format (x_complex): 1st dimension is the current state, 2nd dimension is the previous state,
    #                            first element of each dimension is the real part of the state, second element
    #                            is the imaginary portion of the current state
    x_complex = torch.empty(2,2,dtype=torch.float)

    # Matrix format (z_complex): 1st element is the real value of the current observed state, 2nd element is
    #                            the imaginary portion of the observed state
    z_complex = torch.empty(2, dtype=torch.float)

    # Pre-allocating a matrix to save all true state values, for DEBUGGING
    # Matrix format is batch element in 1st dimension, current and previous state in 2nd dimension,
    # real and complex in the 3rd dimension, sequence element in the 4th dimension,
    # and then series element in the 5th dimension
    all_xs = torch.zeros((batchSize, 2, 2, sequenceLength+1, simLength), dtype=torch.float)

    if(cuda):
        v.cuda()
        w.cuda()

        x_complex.cuda()
        z_complex.cuda()

        z.cuda()
        x.cuda()

        R.cuda()
        Q.cuda()
        QChol.cuda()

        arCoeffMeans.cuda()

        all_xs.cuda()


    ### Loop for generating all the batches of data (a series) ###
    for i in range(0,simLength):
        ## Loop for generating a batch of data ##
        # Iterating through one additional time so that we can get the actual next state
        # and the current actual state
        for j in range(0, batchSize):
            F = ARCoeffecientGeneration(arCoeffMeans, AR_coeffecient_noise_var)
            # Loop for generating the sequence of data for each batch element #
            for m in range(0, sequenceLength + 1):
                # Generate system noise vector
                rSysNoise = torch.div(torch.matmul(QChol,
                                        torch.randn(AR_n, 1)), torch.sqrt(torch.tensor(2, dtype=torch.float)))
                iSysNoise = torch.div(torch.matmul(QChol,
                                        torch.randn(AR_n, 1)), torch.sqrt(torch.tensor(2, dtype=torch.float)))
                # Forced to squeeze the noise values because they needed to be 2x1 tensors to multiply, but v[0]
                # is 2x in dimension (same for v[1])
                v[:,0] = torch.squeeze(rSysNoise)
                v[:,1] = torch.squeeze(iSysNoise)

                # Generate observation noise vector
                rObsNoise = torch.div(torch.matmul(torch.sqrt(R),
                                        torch.randn(1)),torch.sqrt(torch.tensor(2, dtype=torch.float)))
                iObsNoise = torch.div(torch.matmul(torch.sqrt(R),
                                        torch.randn(1)),torch.sqrt(torch.tensor(2, dtype=torch.float)))
                w[0] = torch.squeeze(rObsNoise)
                w[1] = torch.squeeze(iObsNoise)
                # On first iteration through make the noise equal to zero so there the initial state starts at 0
                if(m==0):
                    x_complex = torch.zeros(2,2, dtype=torch.float)
                    z_complex = torch.zeros(2, dtype=torch.float)
                else:
                    # x_complex[:,0] = torch.matmul(F,x_complex[:,0])
                    # x_complex[:,1] = torch.matmul(F, x_complex[:,1])
                    x_complex = torch.matmul(F,x_complex)
                    x_complex = x_complex + v
                    z_complex = x_complex[0] + w

                # Grabbing all true state values to help with DEBUGGING
                # Indexing into x_complex in this way because it has shape (2,1) but we want it to be shaped (2,)
                all_xs[j,:,:,m,i] = x_complex

                # Still in the measurement generation process
                if(m<sequenceLength):
                    # Storing the measured data in its appropriate batch element, its appropriate
                    # complex and real components, its appropriate sequence element, and the right
                    # series element
                    z[j,0,m,i] = z_complex[0]
                    z[j,1,m,i] = z_complex[1]
                # If we are on the sequenceLength + 1 iteration we need to grab the current
                # true state (will be the next predicted true state from the measurements),
                # and the previous actual state (will be the current true state from the
                # measurements)
                if(m==sequenceLength):
                    x[j,0,i] = x_complex[1,0]
                    x[j,1,i] = x_complex[0,0]
                    x[j,2,i] = x_complex[1,1]
                    x[j,3,i] = x_complex[0,1]

                #else:
                 #   x[j,0,i] = x_complex[1].real
                  #  x[j,1,i] = x_complex[0].real
                  #  x[j,2,i] = x_complex[1].imag
                  #  x[j,3,i] = x_complex[0].imag
                # End of sequence generation loop
            # End of batch generation loop
        # End of series generation loop

    ##### Storing the data #####
    storageFilePath = './data'
    dataFile = 'data'
    logContent = {}
    logContent[u'measuredData'] = z.numpy()
    logContent[u'predAndCurState'] = x.numpy()
    logContent[u'allTrueStateValues'] = all_xs.numpy()
    matSave(storageFilePath,dataFile,logContent)

    # Return data
    return(x.numpy(), z.numpy())