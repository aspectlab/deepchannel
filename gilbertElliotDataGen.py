import numpy as np
from scipy import linalg as sciAlg
from utilities import matSave, convertToBatched

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
#                                                                      observed sequence of data created by a a
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


def GilEllDataGen(params, seed=-1):

    if (seed > 0):
        np.random.seed(seed)

    # TODO Error checking: verify that p and q are between 1 and 0
    p,q = params[0]
    transitionProbabiltyArray = ((p, 1-p), (q, 1-q))
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
        elif(MarkovState == 'bad'):
            F = badF
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

        # x_current and z_current are already initialized to zeros before the loop starts, so we don't need to
        # change them at all in the first iteration
        if not (i == 0):
            # Going through the steps of an AR Process
            x_current = np.matmul(F, x_current) + v
            z_current = np.matmul(H,x_current) + w

        z[:,i] = z_current
        x[:,i] = x_current[0]

    return((x, z, riccatiConvergences))

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
        toeplitzFinalTrueStates[0:2,i] = np.real(x[0,i + numColumns:i+numColumns+2])
        # Grabbing the imaginary estimated and predicted true state values
        toeplitzFinalTrueStates[2:4,i] = np.imag(x[0,i+numColumns:i+numColumns+2])
        # Grabbing all the system state values real and imaginary components
        toeplitzAllTrueStates[0, :, i] = np.real(x[0,i:i+numColumns+1])
        toeplitzAllTrueStates[1,:,i] = np.imag(x[0,i:i+numColumns+1])
    return((toeplitzAllTrueStates, toeplitzObservationStates, toeplitzFinalTrueStates))


# GilEllTrainingDataGen: Function that generates training data with from the good and bad coefficients supplied to it.
#                        It will generate 2 times as many sequences of data as the number of sequences specified,
#                        because it will generate two sets of sequences, one from the good coefficients and one from
#                        the bad coefficients, and then randomly shuffle the two sets of sequences together, creating a
#                        training set that can be used to train the TCN and LS
def GilEllTrainingDataGen(sequenceLength=10, numSequences=100, goodCoefficients=[0.5, -0.4],
                          badCoefficients=[1.414, -0.99968], goodTransProb=0.999, badTransProb=0.999, QVar=0.1,
                          RVar=0.1, randSeed=int(np.abs(np.floor(100*np.random.randn(1)))), **kwargs):
    # TODO: Convert this from creating its own data format to the toeplitzified data
    finalTrueStates = np.zeros((4, numSequences*2), dtype=float)
    observationStates = np.zeros((2, sequenceLength, numSequences*2), dtype=float)
    # All system states smashed into one vector
    allTrueStates = np.zeros((2, sequenceLength + 1, numSequences*2), dtype=float)

    for i in range(0, numSequences):
        # Generate a set of data that is only using the good coefficients
        sequenceData = GilEllDataGen([(1, 0), (goodCoefficients, badCoefficients),
                                      sequenceLength, (QVar, RVar), 'good'], seed=randSeed+i)
        # first half of observationsStates and finalTrueStates is from the good state data
        observationStates[0,:,i] = np.real(sequenceData[1][0,0:sequenceLength])
        observationStates[1,:,i] = np.imag(sequenceData[1][0,0:sequenceLength])

        finalTrueStates[0:2, i] = np.real(sequenceData[0][0,sequenceLength-1:sequenceLength+1])
        finalTrueStates[2:4, i] = np.imag(sequenceData[0][0,sequenceLength-1:sequenceLength+1])

        allTrueStates[0,:,i] = np.real(sequenceData[0][0,0:sequenceLength+1])
        allTrueStates[1,:,i] = np.imag(sequenceData[0][0,0:sequenceLength+1])


        # Generate a set of data that is only using the bad coefficients
        sequenceData = GilEllDataGen(((0,1), (goodCoefficients, badCoefficients),
                                     sequenceLength, (QVar, RVar), 'bad'), seed=randSeed+i+numSequences)
        # second half of observationsStates and finalTrueStates is from the bad state data
        observationStates[0,:,i+numSequences-1] = np.real(sequenceData[1][0,0:sequenceLength])
        observationStates[1,:,i+numSequences-1] = np.imag(sequenceData[1][0,0:sequenceLength])

        finalTrueStates[0:2, i+numSequences-1] = np.real(sequenceData[0][0, sequenceLength - 1:sequenceLength + 1])
        finalTrueStates[2:4, i+numSequences-1] = np.imag(sequenceData[0][0, sequenceLength - 1:sequenceLength + 1])

        allTrueStates[0, :, i+numSequences-1] = np.real(sequenceData[0][0, 0:sequenceLength + 1])
        allTrueStates[1, :, i+numSequences-1] = np.imag(sequenceData[0][0, 0:sequenceLength + 1])

    # Creating a set of random indexes so that the data can be shuffled randomly, but we can still have the indexes of
    # the observations line up with the indexes of the finalTrueStates
    shuffleIndexes =  np.random.shuffle(np.arange(finalTrueStates.shape[1]))
    # Shuffling data
    finalTrueStates = np.squeeze(finalTrueStates[:,shuffleIndexes])
    observationStates = np.squeeze(observationStates[:,:,shuffleIndexes])
    allTrueStates = np.squeeze(allTrueStates[:,:,shuffleIndexes])

    # Recovering the Riccati Convergences
    riccatiConvergences = sequenceData[2]

    ##### Storing the data #####
    storageFilePath = './data'
    dataFile = 'GEData'
    logContent = {}
    logContent[u'observedStates'] = observationStates
    logContent[u'systemStates'] = allTrueStates
    logContent[u'finalStateValues'] = finalTrueStates
    logContent[u'seed'] = randSeed
    logContent[u'riccatiConvergences'] = riccatiConvergences
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

    data = (allTrueStates, observationStates, finalTrueStates)
    info = {}
    info[u'filename'] = filename
    info[u'riccatiConvergences'] = riccatiConvergences
    info[u'seed'] =  randSeed

    return(data, info)

def GilElTestDataGen(sequenceLength=10, numSequences=100, goodCoefficients=[0.5, -0.4], testSetLen=1,
                          badCoefficients=[1.414, -0.99968], goodTransProb=0.999, badTransProb=0.999, QVar=0.1,
                          RVar=0.1, randSeed=int(np.abs(np.floor(100*np.random.randn(1)))), batch_size=20, **kwargs):
    LSandKFTestData = []
    testDataInfo = []

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
        # Generating the data with no variance between sequences (which is what the False in the array is for)
        # because we want to generate data with a single set of AR Coefficients
        subsetTestStateData, subsetTestDataInfo = GilElDataGenWrapper(sequenceLength=sequenceLength, numSequences=numSequences,
                                                                      badCoefficients=badCoefficients, goodCoefficients=goodCoefficients,
                                                                      goodTransProb=goodTransProb, badTransProb=badTransProb,
                                                                      RVar=RVar, QVar=QVar, randSeed=randSeed)
        trueStateTEST[k, :, :, :], measuredStateTEST[k, :, :, :, :] = convertToBatched(subsetTestStateData[2],
                                                                                       subsetTestStateData[1],
                                                                                       batch_size)
        # Storing the data that the Least Squares and Kalman Filter will be using
        LSandKFTestData.append(subsetTestStateData)

        subsetInfoHolder = {}
        # Grabbing the first riccatiConvergence because they should all be the same for both the estimate and prediction
        subsetInfoHolder[u'riccatiConvergencePredGoodState'] = subsetTestDataInfo['riccatiConvergences'][0, 0]
        subsetInfoHolder[u'riccatiConvergenceEstGoodState'] = subsetTestDataInfo['riccatiConvergences'][0, 1]
        subsetInfoHolder[u'riccatiConvergencePredBadState'] = subsetTestDataInfo['riccatiConvergences'][1,0]
        subsetInfoHolder[u'riccatiConvergenceEstBadState'] = subsetTestDataInfo['riccatiConvergences'][1,1]

        # This is just for old formatting purposes
        # TODO: Figure out a better way to do this, potentially showing both the good and bad state when the network
        # TODO: loads data from a GE Data file
        subsetInfoHolder[u'riccatiConvergencePred'] = subsetInfoHolder['riccatiConvergencePredGoodState']
        subsetInfoHolder[u'riccatiConvergenceEst'] = subsetInfoHolder['riccatiConvergenceEstGoodState']

        # Grabbing the first set of AR Coefficients from the F matrix because they should all be the same
        subsetInfoHolder[u'ARCoefficients'] = [goodCoefficients, badCoefficients]
        # Grabbing the file path of the data file
        subsetInfoHolder[u'dataFilePath'] = subsetTestDataInfo['filename']
        subsetInfoHolder[u'seed'] = subsetTestDataInfo['seed']
        testDataInfo.append(subsetInfoHolder)
    # Saving relevant data so it can be recovered and reused
    testDataToBeSaved = {}
    testDataToBeSaved[u'trueStateTEST'] = trueStateTEST
    testDataToBeSaved[u'measuredStateTEST'] = measuredStateTEST
    testDataToBeSaved[u'testDataInfo'] = testDataInfo
    testDataToBeSaved[u'LSandKFTestData'] = LSandKFTestData
    testFile = matSave('data', 'GETestData', testDataToBeSaved)
    return(testDataToBeSaved)


def GilElDataGenWrapper(sequenceLength=10, numSequences=100, goodCoefficients=[0.5, -0.4],
                          badCoefficients=[1.414, -0.99968], goodTransProb=0.999, badTransProb=0.999, QVar=0.1,
                          RVar=0.1, randSeed=int(np.abs(np.floor(100*np.random.randn(1)))), **kwargs):
    # Generating a much longer sequence that will have the exact length to cause the toeplitz matrix that it will become
    # to have the exact sequence length and number of sequences that we expect
    longSequenceLength = numSequences + sequenceLength - 1

    # Generating the long sequence of data using the passed params and the calculated length. Want it to start in
    # a random state because this is how we intend to test our system
    longSequence = GilEllDataGen(([goodTransProb, badTransProb], [goodCoefficients, badCoefficients],
                                  longSequenceLength, [QVar, RVar], 'random'), randSeed)
    data = toeplitzData(longSequence, sequenceLength)

    riccatiConvergences = longSequence[2]

    ##### Storing the data #####
    storageFilePath = './data'
    dataFile = 'GEData'
    logContent = {}
    logContent[u'observedStates'] = data[1]
    logContent[u'systemStates'] = data[0]
    logContent[u'finalStateValues'] = data[2]
    logContent[u'seed'] = randSeed
    logContent[u'riccatiConvergences'] = riccatiConvergences
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

    args = parser.parse_args()

    # Setting the args to their appropriate variables
    simuLen = int(args.simu_len)
    sequenceLen = int(args.seq_len)
    seed = args.seed
    testGeneration = args.testDataGen

    # default_q = 0.999
    # default_p = 0.999
    # default_F_p = (0.5, -0.4)
    # default_F_q = (1.414, -0.999698)
    # default_sequence_length = 100
    # default_Covariances = (0.1, 0.1)
    # defaultParams = [(default_p, default_q), (default_F_p, default_F_q), default_sequence_length,
    #                  default_Covariances]
    # test = GilEllDataGen(defaultParams)
    # toepObs, toepTrue = toeplitzData(test, 3)
    #
    # test2 = GilEllTrainingDataGen(sequenceLength=10, numSequences=10)

    start = time.time()
    if not testGeneration:
        data = GilElDataGenWrapper(numSequences=simuLen, sequenceLength=sequenceLen, randSeed=seed)
    else:
        data = GilElTestDataGen(numSequences=simuLen, sequenceLength=sequenceLen, randSeed=seed)

    end = time.time()

    runTime = end - start
    print('it took {} seconds for this process to run'.format(runTime))