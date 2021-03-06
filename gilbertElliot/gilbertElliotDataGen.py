import numpy as np
from scipy import linalg as sciAlg
import hdf5storage as hdf5s
import os
import os.path as path

# matSave: Function that saves data to a specified .mat file, with the specific file it will be
#          saved to being 'directory/basename{#}.mat', where # is the lowest number that will
#          not save over another file with the same basename
#   Inputs: (directory, basename, data)
#       directory (str) - the directory for the data to be saved in
#       basename (str) - the name of the file you want the data saved to before the appended number
#       data (dict) - a dict of data to be saved to the .mat file
#   Outputs: (logName)
#       logName (str) - the name of the file that the data was saved to
def matSave(directory, basename, data):
    # Create the data directory if it doesn't exist
    if not (path.exists(directory)):
        os.mkdir(directory, 0o755)
    fileSpaceFound = False
    logNumber = 0
    # Creating the log file in a new .mat file that doesn't already exist
    while (not fileSpaceFound):
        logNumber += 1
        logName = directory + '/' + basename + str(logNumber) + '.mat'
        if not (path.exists(logName)):
            print('data saved to: ', logName)
            fileSpaceFound = True
    # Saving the data to the log file
    hdf5s.savemat(logName, data)
    return(logName)

def convertToBatched(systemDataToBeConverted, observedDataToBeFormatted, batchSize):
    numSequences = observedDataToBeFormatted.shape[2]
    seqLength = observedDataToBeFormatted.shape[1]
    seriesLength = int(numSequences/batchSize)

    trueState = np.empty((batchSize, 4, seriesLength), dtype=float)
    measuredState = np.empty((batchSize, 2, seqLength, seriesLength), dtype=float)

    for i in range(seriesLength):
        trueState[:, :, i] = np.transpose(systemDataToBeConverted[:, i * batchSize:(i + 1) * batchSize])
        measuredState[:, :, :, i] = np.swapaxes(
            np.transpose(observedDataToBeFormatted[:, :, i * batchSize:(1 + i) * batchSize]), 1, 2)
    return(trueState, measuredState)

# TODO: Make this and the following function more general, so they could
# TODO: be used for shuffling matrices of any shape and dimensionality
def shuffleMeasTrainData(dataToBeShuffled):
    import torch as t
    dataDims = dataToBeShuffled.shape
    shuffledData = t.zeros(dataDims)

    totalDims = dataDims[0] * dataDims[3]
    
    randomPermutation = t.randperm(totalDims)
    cnt = -1
    for m in range(0, dataDims[0]):
        for n in range(0, dataDims[3]):
            cnt = cnt + 1
            i = randomPermutation[cnt] % dataDims[0]
            j = randomPermutation[cnt] // dataDims[0]

            shuffledData[m, :, :, n] = dataToBeShuffled[i, :, :, j]

    return (shuffledData, randomPermutation)


def shuffleTrueTrainData(dataToBeShuffled, randomPermutation):
    import torch as t
    dataDims = dataToBeShuffled.shape
    shuffledData = t.zeros(dataDims)
    cnt = -1
    for m in range(0, dataDims[0]):
        for n in range(0, dataDims[2]):
            cnt = cnt + 1
            i = randomPermutation[cnt] % dataDims[0]
            j = randomPermutation[cnt] // dataDims[0]

            shuffledData[m, :, n] = dataToBeShuffled[i, :, j]

    return shuffledData




# GilEllDataGen: Function that generates a sequence of data from an AR Process who's coefficients are subject to
#                a Gilbert-Elliot model. This means that the data will be generated from two sets of AR Coefficients,
#                and it will switch between the two sets (here on called "good" and "bad" states) based on a two state
#                Markov Chain
#   Inputs: (params, seed)
#         params (tuple/list): Parameters for the data generation process
#           params[0] (tuple/list) - (p,q): A list of floats that correspond to the transition probabilities of the
#                                    Markov Chain
#               params[0][0] (float) - p: The probability of transitioning from the "good" state to the "bad" state
#                                         in the Markov Chain
#               params[0][1] (float) - q: The probability of transitioning from the "bad" state to the "good" state
#           params[1] (tuple/list) - ([F_p1, F_p2], [F_q1, F_q2]): A tuple/list of tuples that corresponds to the
#                                     AR_Coefficients of the good and bad states
#               params[1][0] (tuple/list) - [F_p1, F_p2]: AR Coefficients of the good state
#                   params[1][0][0] (float) - F_p1: First AR Coefficient of the good state
#                   params[1][0][1] (float) - F_p2: Second AR Coefficient of good state
#               params[1][1] (tuple/list) - [F_q1, F_q2]: AR Coefficients of the bad state
#                   params[1][1][0] (float) - F_q1: First AR Coefficient of bad state
#                   params[1][1][1] (float) - F_q2: Second AR Coefficient of bad state
#           params[2] (int) - sequenceLength: Length of the sequence of data to be generated
#           params[3] (tuple/list) - [Q_diag,R]: List of the covariances of the AR Process Noises
#               params[3][0] (float) - Q_diag = 0.1: The upper left number in the Q matrix that forms the covariance
#                                               matrix of the AR system noise v[k] {Default=0.1}
#               params[3][1] (float) - R = 0.1: The covariance of the AR observation noise w[k] {Default=0.1}
#           params[4] (str) - startState =  'good': A string that tells you which state the Markov Chain should
#                                                   start in, the 3 options supported at this time are 'good'
#                                                   which causes the system to start in the good state, 'bad'
#                                                   which causes the system to start in the bad state, and
#                                                   'random', which starts the system in a random state, with a 50/50
#                                                   chance of starting in either state. {Default='good'}
#       seed=-1 (int) - The seed of the RNG state that this function uses to generate random numbers. If this
#                       value is less than 1, then it will be ignored, and no seed will be set {default=-1}
#   Outputs: (sequenceData)
#       sequenceData (tuple) - A tuple that contains the data that was generated by the Gilbert Elliot AR Process
#           sequenceData[0] (complex128 np.matrix) - x: A sequence of complex numbers that form the
#                                                                  system states of a Gilbert-Elliot AR Process
#           sequenceData[1] (complex128 np.matrix) - z: A sequence of complex numbers that form the
#                                                                      observed sequence of data created by the
#                                                                      Gilbert-Elliot AR Process
#           sequenceData[2] (np.matrix) - ricattiConvergences: The matrix containing the Ricatti Convergences of the two
#                                                              sets of AR Coefficients, organized with the 1st dimension
#                                                              consisting of the MSE convergence of the prediction and
#                                                              estimate of the good Markov State, and the 2nd dimension
#                                                              of the MSE convergence of the prediction and estimate of
#                                                              the bad Markov State. The following visual provides
#                                                              further documentation:
#                                                              [[ goodStatePredictionMSE, goodStateEstimateMSE ],
#                                                               [ badStatePredictionMSE, badStateEstimateMSE]]
#               riccatiConvergences[0,0] - Riccati MSE of good state prediction
#               riccatiConvergences[0,1] - Riccati MSE of good state estimate
#               riccatiConvergences[1,0] - Riccati MSE of bad state prediction
#               riccatiConvergences[1,1] - Riccati MSE of bad state estimate


def GilEllDataGen(params, seed=-1, debug=False, **kwargs):

    if (seed > 0):
        np.random.seed(seed)

    # TODO Error checking: verify that p and q are between 1 and 0
    p,q = params[0]
    transitionProbabiltyArray = ((1-p, p), (1-q, q))
    transitionStateArray = [['good', 'bad'], ['bad', 'good']]

    goodCoeffs = np.array(params[1][0])
    badCoeffs = np.array(params[1][1])

    sequenceLength = params[2]

    ### Setting up the Q_diag and R parameters ###
    # If this parameter was never specified in the passed parameters set both to defaults
    if(len(params) < 4):
        Q_diag = 0.1
        R = 0.1
    # If a list or tuple with a single item was passed, then assume it was the Q_diag component and default R
    elif(len(params[3]) == 1):
        Q_diag=params[3][0]
        R = 0.1
    # if a float was passed then assume that it was the Q_diag component, and default R
    elif(type(params[3]) is float):
        Q_diag = params[3]
        R = 0.1
    # Otherwise assume that both R and Q_diag were passed, and set them appropriately
    else:
        Q_diag = params[3][0]
        R = params[3][1]

    # Setting up the starting state of the Markov Chain
    if(len(params) < 5):
        MarkovState = 'good'
    elif(params[4] == 'good'):
        MarkovState = 'good'
    elif(params[4] == 'bad'):
        MarkovState = 'bad'
    elif(params[4] == 'random'):
        startingStates = ['good', 'bad']
        startingProbabilities = [0.5, 0.5]
        MarkovState = np.random.choice(startingStates, replace=True, p=startingProbabilities)

    ### Setting up the AR Process Variables ###

    # Noise covariance matrix / noise mean
    Q = np.matrix([[Q_diag, 0], [0, 0]])
    QChol = np.matrix([[np.sqrt(Q_diag), 0], [0, 0]])

    # Observation covariance matrix/ noise mean
    R = np.matrix([R])

    # Matrix mapping real states into observation domain (required for Riccati Equation)
    H = np.matrix([1, 0])

    # Pre-allocating the matrix that will store the true values of the system state
    x = np.empty([1, sequenceLength+1], dtype=complex)
    # Pre-allocating the current true state to be used in the AR Process equation
    x_current = np.zeros([2,1], dtype=complex)

    # Pre-allocating the matrix that will store the observed states
    z = np.empty([1, sequenceLength+1], dtype=complex)

    # Pre-allocating the current observation state matrix
    z_current = np.zeros([1], dtype=complex)

    # Pre-allocating for the system noise vector
    v = np.empty([2,1], dtype=complex)

    # Pre-allocating for the observation noise vector
    w = np.empty(1, dtype=complex)


    ### Computing the Riccati Convergences of the good and bad Markov states ###
    # Setting up the matrices that will be used for the equations
    riccatiConvergences = np.empty((2,2), dtype=float)
    goodF = np.matrix([goodCoeffs, [1, 0]])
    badF = np.matrix([badCoeffs, [1,0]])
    # Computing the Riccati Convergences of the two sets of Coefficients
    riccatiPredGood = sciAlg.solve_discrete_are(np.transpose(goodF), np.transpose(H), Q, R)
    kRicConIntermediate = np.add(np.matmul(np.matmul(H, riccatiPredGood), np.transpose(H)), R)
    riccatiKalGain = np.matmul(np.matmul(riccatiPredGood, np.transpose(H)), np.linalg.inv(kRicConIntermediate))

    # Computing the Riccati Equation for the good state AR process Estimate
    riccatiEstGood = riccatiPredGood - (np.matmul(np.matmul(riccatiKalGain, H), riccatiPredGood))

    riccatiPredBad = sciAlg.solve_discrete_are(np.transpose(badF), np.transpose(H), Q, R)
    kRicConIntermediate = np.add(np.matmul(np.matmul(H, riccatiPredBad), np.transpose(H)), R)
    riccatiKalGain = np.matmul(np.matmul(riccatiPredBad, np.transpose(H)), np.linalg.inv(kRicConIntermediate))

    # Computing the Riccati Equation for the good state AR process Estimate
    riccatiEstBad = riccatiPredBad - (np.matmul(np.matmul(riccatiKalGain, H), riccatiPredBad))

    # Assigning the ricatttiConvergences matrix the correct values
    riccatiConvergences[0,0] = riccatiPredGood[0,0]
    riccatiConvergences[0,1] = riccatiEstGood[0,0]
    riccatiConvergences[1,0] = riccatiPredBad[0,0]
    riccatiConvergences[1,1] = riccatiEstBad[0,0]
    
    # Saving Channel States for Genie Kalman Filter
    channelStates = np.empty([2, sequenceLength + 1])
    
    if(debug):
        w_all = np.zeros((1, sequenceLength + 1), dtype=complex)
        v_all = np.zeros((2, sequenceLength + 1), dtype=complex)
        # Doesn't need to be here, but just documenting 
        # it show that its only included if debug == True
        x_start = np.zeros((2, 1), dtype=complex)

    # Main loop generating the sequence of data
    for i in range(0,sequenceLength + 1):

        # Logic to decided the next Markov State
        # Skips the first iteration since that is what the Markov State was initialized for
        if not(i == 0):
            # Transition Calculation from good state
            if(MarkovState == 'good'):
                MarkovState = np.random.choice(transitionStateArray[0], replace=True, p=transitionProbabiltyArray[0])
            # Transition Calculation from bad state
            elif(MarkovState == 'bad'):
                MarkovState = np.random.choice(transitionStateArray[1], replace=True, p=transitionProbabiltyArray[1])
            # Throw an error if you are ever not in the good or bad state
            else:
                raise Exception('This shouldn\'t be able to happen, something has gone awry, and you are outside the'
                                'defined Markov States. Current state is: {}'.format(MarkovState))
        if(MarkovState == 'good'):
            F = goodF
            channelStates[:, i] = goodCoeffs
        elif(MarkovState == 'bad'):
            F = badF
            channelStates[:,i] = badCoeffs
        else:
            raise Exception('This shouldn\'t be able to happen, something has gone awry, and you are outside the'
                            'defined Markov States. Current state is: {}'.format(MarkovState))

        # AR Process computation for one time stamp
        # Generate system noise vector
        rSysNoise = np.divide(np.matmul(QChol, np.random.randn(2,1)), np.sqrt(2))
        iSysNoise = 1j * np.divide(np.matmul(QChol, np.random.randn(2,1)), np.sqrt(2))

        v = rSysNoise + iSysNoise

        rObsNoise = np.divide(np.matmul(np.sqrt(R), np.random.randn(1)), np.sqrt(2))
        iObsNoise = 1j * np.divide(np.matmul(np.sqrt(R), np.random.randn(1)), np.sqrt(2))

        w = rObsNoise + iObsNoise

        if(debug):
            v_all[:,i] = np.squeeze(v)
            w_all[:,i] = w
        # x_current and z_current are already initialized to zeros before the loop starts, so we don't need to
        # change them at all in the first iteration
        if not (i == 0):
            # Going through the steps of an AR Process
            x_current = np.matmul(F, x_current) + v
            
        else:
            # Start the channel with a zero mean unity variance random sample
            x_current = (np.divide(np.random.randn(2,1), np.sqrt(2))) + \
                        (1j * np.divide(np.random.randn(2,1), np.sqrt(2)))
            if(debug):
                x_start = x_current
        z_current = np.matmul(H,x_current) + w
        
        z[:,i] = z_current
        x[:,i] = x_current[0]
    if(debug):
        debugData = dict()
        debugData['x_init'] = x_start
        debugData['v_all'] = v_all
        debugData['w_all'] = w_all
        matSave('data', 'debugData', debugData)

    return((x, z, riccatiConvergences, channelStates))

# toeplitzData: Function that converts a sequence of data generated by the GilEllDataGen to a toeplitz matrix of
#               observations with dimensions (2 x matrixRowLength x N) after seperating the complex numbers into their
#               real and imaginary components, and also generates a (4 x N) matrix of the real and imaginary components
#               of the current and next true states for each row of the toeplitz matrix
#   Inputs: (dataSequence, matrixRowLength)
#       sequenceData (tuple) - The direct output of the GilEllDataGen function (see GilEllDataGen output: sequenceData)
#       matrixRowLength (int) - The number of columns of the toeplitz observation matrix that will be output from this
#                               function. Is also used to generate the number rows of both the toeplitz observation and
#                               true state toeplitz matrices using the equation: numRows = sequenceLength - numCols + 1
#                               Will throw an error if the you try to specify that the number of rows should be greater
#                               than the length of sequence data fed into the function
#   Outputs: (toeplitzObservationStates, toeplitzTrueStates)
#       toeplitzStates (tuple) - tuple containing the true states, observation states and finalTrueStates of the data
#          toeplitzAllTrueStates (np.matrix, float) - A (2 x numColumns+1 x N) toeplitz matrix created from the system
#                                                     states that can be used to train the LS algorithm
#          toeplitzObservationStates (np.matrix, float) - A (2 x numColumns x N) toeplitz matrix created from
#                                                         the observation states of the sequence (also converts
#                                                         complex numbers to real and imaginary components
#          toeplitzFinalTrueStates (np.matrix, float) - A (4 x N) matrix that contains the complex numbers representing the
#                                                       current and next true states of each row of the
#                                                       toeplitzObservationStates (also converts complex numbers to real
#                                                       and imaginary components)

#
# Notes: * N is used in the above documentation, which is the number of rows of both the toeplitzObservationStates and
#          toeplitzTrueStates matrices, and is calculated from: N = sequenceLength - matrixRowLength + 1

def toeplitzData(sequenceData, numColumns):
    # The sequence length is the number of data points in the data generated, minus 1 so their can be a final
    # next state for prediction purposes
    sequenceLength = sequenceData[0].shape[1] - 1
    numRows = sequenceLength - numColumns + 1

    x = sequenceData[0]
    z = sequenceData[1]

    if(numRows < 1):
        raise Exception('Cannot create a toeplitz matrix from data sequence with sequence length: {1}, and number of '
                        'toeplitz rows: {2}'.format(sequenceLength, numColumns))

    toeplitzObservationStates = np.empty((2, numColumns, numRows), dtype=float)
    toeplitzFinalTrueStates = np.empty((4, numRows), dtype=float)
    toeplitzAllTrueStates = np.empty((2, numColumns + 1, numRows), dtype=float)

    # Creating the toeplitz matrices
    for i in range(0, numRows):
        toeplitzObservationStates[0,:, i] = np.real(z[0,i:i + numColumns])
        toeplitzObservationStates[1,:,i] = np.imag(z[0,i:i+numColumns])
        # Grabbing the real estimated and predicted true state values
        toeplitzFinalTrueStates[0:2,i] = np.real(x[0,i + numColumns-1:i+numColumns+1])
        # Grabbing the imaginary estimated and predicted true state values
        toeplitzFinalTrueStates[2:4,i] = np.imag(x[0,i+numColumns-1:i+numColumns+1])
        # Grabbing all the system state values real and imaginary components
        toeplitzAllTrueStates[0, :, i] = np.real(x[0,i:i+numColumns+1])
        toeplitzAllTrueStates[1,:,i] = np.imag(x[0,i:i+numColumns+1])
    return((toeplitzAllTrueStates, toeplitzObservationStates, toeplitzFinalTrueStates))



# GilElTestDataGen: Function that uses the GilElDatagenWrapper to generate a set of data that has everything required
#                   for a test data set that can be fed right into the TCN
def GilElTestDataGen(sequenceLength=10, numSequences=100, goodCoefficients=[0.3, 0.1],
                          badCoefficients=[1.949, -0.95], goodTransProb=0.0005, 
                          badTransProb=0.0005, QVar=0.1, RVar=0.1, 
                          randSeed=int(np.abs(np.floor(100*np.random.randn(1)))), 
                          batch_size=20, testSetLen=3, initTest=False, debug=False,  **kwargs):
    LSandKFTestData = []
    testDataInfo = []

    # For right now we will be hard coding this to be 3, because we want to generate a good set of coefficients,
    # a bad set, and a set that is generated from both sets
    # testSetLen = 3

    numBatchedSequences = int(numSequences/batch_size)
    # trueStateDataTEST Dimensionality: comprised of sets of data based on the number of AR
    #                                   coefficients that are to be generated in the 1st
    #                                   dimension, then of batch elements in the 2nd
    #                                   dimension, real and imaginary portions of the true state
    #                                   in the 3rd dimension, and by batches in the 4th dimension
    trueStateTEST = np.empty((testSetLen, batch_size, 4, numBatchedSequences), dtype=float)

    # measuredStateTEST Dimensionality: comprised of sets of data based on the number of AR
    #                                   coefficients used for testing in the 1st dimension,
    #                                   batch elements in the 2nd dimension, real and complex
    #                                   values in the 3rd dimension, sequence elements in the
    #                                   4th dimension, and by batches in the 5th dimension

    measuredStateTEST = np.empty((testSetLen, batch_size, 2, sequenceLength, numBatchedSequences), dtype=float)

    for k in range(0, testSetLen):
        # Generate data from both the good and bad coefficients
        if(k==0):

            # Generating the data with no variance between sequences (which is what the False in the array is for)
            # because we want to generate data with a single set of AR Coefficients
            subsetTestStateData, subsetTestDataInfo = GilElDataGenWrapper(sequenceLength=sequenceLength, numSequences=numSequences,
                                                                          badCoefficients=badCoefficients, goodCoefficients=goodCoefficients,
                                                                          goodTransProb=goodTransProb, badTransProb=badTransProb,
                                                                          RVar=RVar, QVar=QVar, randSeed=randSeed, initTest=initTest,
                                                                          debug=debug)
            trueStateTEST[k, :, :, :], measuredStateTEST[k, :, :, :, :] = convertToBatched(subsetTestStateData[2],
                                                                                           subsetTestStateData[1],
                                                                                           batch_size)
            # Storing the data that the Least Squares and Kalman Filter will be using
            LSandKFTestData.append(subsetTestStateData)

            subsetInfoHolder = {}

            # Displaying the average Riccati Convergence of the data
            subsetInfoHolder[u'riccatiConvergencePred'] = (subsetTestDataInfo['riccatiConvergences'][1,0] +
                                                          subsetTestDataInfo['riccatiConvergences'][0,0])/2
            subsetInfoHolder[u'riccatiConvergenceEst'] = (subsetTestDataInfo['riccatiConvergences'][1,1] +
                                                          subsetTestDataInfo['riccatiConvergences'][0,1])/2

            # Grabbing the first set of AR Coefficients from the F matrix because they should all be the same
            subsetInfoHolder[u'ARCoefficients'] = [goodCoefficients, badCoefficients]
            subsetInfoHolder['transitionProbabilities'] = [goodTransProb, badTransProb]
            # Grabbing the file path of the data file
            subsetInfoHolder[u'dataFilePath'] = subsetTestDataInfo['filename']
            subsetInfoHolder[u'seed'] = subsetTestDataInfo['seed']
            subsetInfoHolder['channelCoefficients'] = subsetTestDataInfo['channelCoefficients']
            testDataInfo.append(subsetInfoHolder)
        # Generate data from the good coefficients only
        elif(k==1):
            # Generating the data with no variance between sequences (which is what the False in the array is for)
            # because we want to generate data with a single set of AR Coefficients
            subsetTestStateData, subsetTestDataInfo = GilElDataGenWrapper(sequenceLength=sequenceLength,
                                                                          numSequences=numSequences,
                                                                          badCoefficients=badCoefficients,
                                                                          goodCoefficients=goodCoefficients,
                                                                          goodTransProb=0,
                                                                          badTransProb=1,
                                                                          RVar=RVar, QVar=QVar,
                                                                          randSeed=randSeed,
                                                                          startingState='good')
            trueStateTEST[k, :, :, :], measuredStateTEST[k, :, :, :, :] = convertToBatched(subsetTestStateData[2],
                                                                                           subsetTestStateData[1],
                                                                                           batch_size)
            # Storing the data that the Least Squares and Kalman Filter will be using
            LSandKFTestData.append(subsetTestStateData)

            subsetInfoHolder = {}

            # Displaying the Riccati Convergences of the good states
            subsetInfoHolder[u'riccatiConvergencePred'] = subsetTestDataInfo['riccatiConvergences'][0,0]
            subsetInfoHolder[u'riccatiConvergenceEst'] = subsetTestDataInfo['riccatiConvergences'][0,1]

            # Grabbing the first set of AR Coefficients from the F matrix because they should all be the same
            subsetInfoHolder[u'ARCoefficients'] = [goodCoefficients, badCoefficients]
            subsetInfoHolder['transitionProbabilities'] = [0, 1]
            # Grabbing the file path of the data file
            subsetInfoHolder[u'dataFilePath'] = subsetTestDataInfo['filename']
            subsetInfoHolder[u'seed'] = subsetTestDataInfo['seed']
            subsetInfoHolder['channelCoefficients'] = subsetTestDataInfo['channelCoefficients']
            testDataInfo.append(subsetInfoHolder)
        # Generate data from the bad coefficients
        elif(k == 2):
            # Generating the data with no variance between sequences (which is what the False in the array is for)
            # because we want to generate data with a single set of AR Coefficients
            subsetTestStateData, subsetTestDataInfo = GilElDataGenWrapper(sequenceLength=sequenceLength,
                                                                          numSequences=numSequences,
                                                                          badCoefficients=badCoefficients,
                                                                          goodCoefficients=goodCoefficients,
                                                                          goodTransProb=1,
                                                                          badTransProb=0,
                                                                          RVar=RVar, QVar=QVar,
                                                                          randSeed=randSeed,
                                                                          startingState='bad', 
                                                                          debug=debug)

            trueStateTEST[k, :, :, :], measuredStateTEST[k, :, :, :, :] = convertToBatched(subsetTestStateData[2],
                                                                                           subsetTestStateData[1],
                                                                                           batch_size)
            # Storing the data that the Least Squares and Kalman Filter will be using
            LSandKFTestData.append(subsetTestStateData)

            subsetInfoHolder = {}

            # Displaying the Riccati Convergence of the bad state coefficients
            subsetInfoHolder[u'riccatiConvergencePred'] = subsetTestDataInfo['riccatiConvergences'][1,0]
            subsetInfoHolder[u'riccatiConvergenceEst'] = subsetTestDataInfo['riccatiConvergences'][1,1]

            # Grabbing the first set of AR Coefficients from the F matrix because they should all be the same
            subsetInfoHolder[u'ARCoefficients'] = [goodCoefficients, badCoefficients]
            subsetInfoHolder['transitionProbabilities'] = [1, 0]
            # Grabbing the file path of the data file
            subsetInfoHolder[u'dataFilePath'] = subsetTestDataInfo['filename']
            subsetInfoHolder[u'seed'] = subsetTestDataInfo['seed']
            subsetInfoHolder['channelCoefficients'] = subsetTestDataInfo['channelCoefficients']
            testDataInfo.append(subsetInfoHolder)
    # Saving relevant data so it can be recovered and reused
    testDataToBeSaved = {}
    testDataToBeSaved[u'trueStateTEST'] = trueStateTEST
    testDataToBeSaved[u'measuredStateTEST'] = measuredStateTEST
    testDataToBeSaved[u'testDataInfo'] = testDataInfo
    testDataToBeSaved[u'LSandKFTestData'] = LSandKFTestData
    testFile = matSave('data', 'GETestData', testDataToBeSaved)
    return(testDataToBeSaved)

# TODO: Add argument to choose whether to save the data or not
def GilElDataGenWrapper(sequenceLength=10, numSequences=100, 
                          goodCoefficients=[0.3, 0.1],
                          badCoefficients=[1.949, -0.95], 
                          goodTransProb=0.0005, badTransProb=0.0005, QVar=0.1,
                          RVar=0.1, 
                          randSeed=int(np.abs(np.floor(100*np.random.randn(1)))),
                          startingState='random', initTest='False', debug=False, **kwargs):
    # Generating a much longer sequence that will have the exact length to cause the toeplitz matrix that it will become
    # to have the exact sequence length and number of sequences that we expect
    longSequenceLength = numSequences + sequenceLength - 1

    # Generating the long sequence of data using the passed params and the calculated length. Want it to start in
    # a random state because this is how we intend to test our system
    longSequence = GilEllDataGen(([goodTransProb, badTransProb], [goodCoefficients, badCoefficients],
                                  longSequenceLength, [QVar, RVar], startingState), randSeed, debug=debug)
    # If we want to test the initializations of the TCN and LS we 
    # zero out the first seq_len number of samples
    if(initTest):
        # Setting the initial values of the sequences here
        inter1 = longSequence[0]
        sShape = inter1.shape

        trueStates = np.zeros(sShape, dtype=np.complex128)
        trueStates[:, sequenceLength:-1] = inter1[:, 0:sShape[1] - (sequenceLength+1)]
        trueStates[:, -1] = inter1[:, -1]

        # Setting the measured states here
        inter1 = longSequence[1]
        sShape = inter1.shape

        measStates = np.zeros(sShape, dtype=np.complex128)
        measStates[:, sequenceLength+1:-1] = inter1[:, 1:sShape[1] - (sequenceLength + 1)]
        measStates[:, -1] = inter1[:, -1]

        inter1 = longSequence[3]
        channelCoeffs = np.zeros(inter1.shape)
        channelCoeffs[:, sequenceLength:-1] = inter1[:, 0:sShape[1] - (sequenceLength + 1)]
        channelCoeffs[:, -1] = inter1[:, -1]


        longSequence = (trueStates, measStates, longSequence[2], channelCoeffs)

        

    data = toeplitzData(longSequence, sequenceLength)

    riccatiConvergences = longSequence[2]
    channelCoefficients = longSequence[3]

    ##### Storing the data #####
    storageFilePath = './data'
    dataFile = 'GEData'
    logContent = {}
    logContent[u'observedStates'] = data[1]
    logContent[u'systemStates'] = data[0]
    logContent[u'finalStateValues'] = data[2]
    logContent[u'seed'] = randSeed
    logContent[u'riccatiConvergences'] = riccatiConvergences
    logContent[u'channelCoefficients'] = channelCoefficients
    logContent[u'parameters'] = {
        "goodCoeffs": goodCoefficients,
        "badCoeffs": badCoefficients,
        "sequenceLength": sequenceLength,
        "numSequences": numSequences,
        "Rvar": RVar,
        "QVar": QVar,
        "goodTransProb": goodTransProb,
        "badTransProb": badTransProb
    }
    filename = matSave(storageFilePath, dataFile, logContent)

    info = {}
    info[u'filename'] = filename
    info[u'riccatiConvergences'] = riccatiConvergences
    info[u'channelCoefficients'] = channelCoefficients
    info[u'seed'] = randSeed
    return(data, info)


if __name__ == "__main__":
    import argparse
    import time

    # Command Line argument parsing if this file is called directly
    parser = argparse.ArgumentParser(description='GEDataGeneration - Generating Data from a Gilbert-Elliot channel model')

    # Sequence Length
    parser.add_argument('--seq_len', type=float, default=20,
                        help='the length of the data sequences (default: 20)')

    # Number of Sequence Samples
    parser.add_argument('--simu_len', type=float, default=100,
                        help='number of sequences of data to generate (default: 100)')

    parser.add_argument('--seed', type=int, default=100,
                        help='seed that sets the RNG state of the data generation process (default: 100)')

    parser.add_argument('--testDataGen', action='store_true',
                        help='specifies whether it should generate a test data set or not (default: False)')

    parser.add_argument('--transProbs', nargs='+', default=['0.0005', '0.0005'],
                        help='probabilities of transitioning from the good to bad and from bad to good '
                             'states (respectfully) of the Markov Chain (default: [0.0005, 0.0005])')
    parser.add_argument('--noMismatchDataGen', action='store_true',
                         help='specifies whether this simulation is supposed to generate No Mimatch Data, combines with --testDataGen to generate test data for the No Mismatch Scenario (default: False)')
    parser.add_argument('--initTest', action='store_true',
                        help='specifies that this data should be padded'
                        'with zeros so that we can test the TCN and LS'
                        'on init of system (default=False)')
    parser.add_argument('--debug', action='store_true', 
                        help='record various variables and other features'
                        'explicitely intended to help with debugging (default=False)')

    parser.add_argument('--ARCoeffs', nargs='+', default=[0.3, 0.1],
                    help='Coefficients Passed to the Kalman Filter, will depend on the scenario you are looking at (default: [0.3, 0.1]')
    args = parser.parse_args()

    # Setting the args to their appropriate variables
    simuLen = int(args.simu_len)
    sequenceLen = int(args.seq_len)
    seed = args.seed
    testGeneration = args.testDataGen
    nonMDG = args.noMismatchDataGen
    goodTransProb = float(args.transProbs[0])
    badTransProb = float(args.transProbs[1])
    initTest = args.initTest
    debugMode = args.debug
    print(args)

    start = time.time()
    if not nonMDG:
        if not testGeneration:
            _ = GilElDataGenWrapper(numSequences=simuLen, sequenceLength=sequenceLen, randSeed=seed,
                                   goodTransProb=goodTransProb, badTransProb=badTransProb, debug=debugMode)
        else:
            _ = GilElTestDataGen(numSequences=simuLen, sequenceLength=sequenceLen, randSeed=seed,
                                goodTransProb=goodTransProb, badTransProb=badTransProb, initTest=initTest, debug=debugMode)
    else:
        coeffs = []
        for ARCoeff in args.ARCoeffs:
            coeffs.append(float(ARCoeff))
        if not testGeneration:
            _ = GilElDataGenWrapper(numSequences=simuLen, sequenceLength=sequenceLen,
                                    randSeed=seed,
                                    goodTransProb=0, badTransProb=1.0,
                                    goodCoefficients=coeffs, 
                                    badCoefficients=coeffs, startingState='good',
                                    debug=debugMode)
        else:
            _ = GilElTestDataGen(numSequences=simuLen, sequenceLength=sequenceLen, 
                    randSeed=seed, goodTransProb=0, 
                    badTransProb=1.0, testSetLen=1, 
                    goodCoefficients=coeffs, badCoefficients=coeffs,
                    startingState='good', initTest=initTest,
                    debug=debugMode)

    end = time.time()

    runTime = end - start
    print('it took {} seconds for this process to run'.format(runTime))
