%% Version history:
% v1.0, 9/27/2020, AGKlein, Initial version
% v1.1, 9/29/2020, AGKlein, Tweaked numerical stability checking in Lambda and get_f_x, changed 
%                           initialization of M to accommodate newly added unknown starting position,
%                           fixed bug in forming final output prediction -- use mu(:,n-1) instead of mu(:,n)

%% Description:
% This script accepts as input a file of data generated by maneuvering.m, and uses
% the data to compute state estimates using an IMM, largely taken from
% Section 11.6 of Bar-Shalom's "Estimation with Applications to Tracking and Navigation".
% Note that this script uses the notation "M" in place of what Bar-Shalom
% calls "P" since we use P for the Markov transition matrix.


%% tweakable system parameters
infile = 'test3.mat';       % file of input data (target trajectories, system parameters)
outfile = 'test3_imm.mat';  % file where results of IMM get saved

%% load data from file, do some renaming of variables, free up some memory
load(infile);
x=x_imm;
z=z_imm;
seqLength = size(XX,2);
[~,N2,numSims]=size(x);
clear XX YY x_imm z_imm

%% non-tweakable parameters and intermediate variables
G=[T^2/2 0; T 0; 0 T^2/2; 0 T];
H=[1 0 0 0 0; 0 0 1 0 0];
numModes = size(P,1);               % number of modes (probably 2 for this project)

%% allocate space and initialize
x_hat_imm=zeros(5,N2);              % allocate space for x_hat_imm (mixed estimate)
x_hat_pred_imm=zeros(5,N2);         % allocate space for x_hat_pred_imm (mixed prediction)
x_hat=zeros(5,numModes,N2);         % allocate space for x_hat (model estimates), and implictly initialize [zero mean assumption]
x_hat_pred=zeros(5,numModes,N2);    % allocate space for x_hat_pred (model estimates)
sampleM=zeros(2,2,N2);              % allocate space for sampleM (sample mean squared error)
sampleM_pred=zeros(2,2,N2);         % allocate space for sampleM_pred (sample predicted mean squared error)
mu=zeros(numModes,N2);              % allocate space for mixing weights
mu(:,1)=ones(numModes,1)/numModes;  % initialize weights (equally likely to be in either state at start)
M=zeros(5,5,numModes,N2);           % allocate space for M (MSE covariance matrix), and initialize
temp=(velocity_init_mean^2+velocity_init_var)/2;                % temp var used in initializing M
temp=diag([position_init_var/2 temp position_init_var/2 temp]);
M(:,:,1,1) = [temp zeros(4,1); zeros(1,4) 0];  % CV mode init
M(:,:,2,1) = [temp zeros(4,1); zeros(1,4) (Om_init_mean^2+Om_init_var)]; % CT mode init
M0 = zeros(5,5,numModes);           % allocate space for mixed state covariance matrix
Lambda=zeros(numModes,1);           % allocate space for likelihoods

%% main loop
fprintf('Processing...')
for k=1:numSims
    for n=2:N2
        
        % interaction / mixing
        c_bar=P'*mu(:,n-1);                     % normalizing factors for mixing probabilities (11.6.6-8)
        MU = diag(mu(:,n-1))*P*diag(1./c_bar);  % mixing probabilities (11.6.6-7)
        X_hat_0 = x_hat(:,:,n-1)*MU;            % mixed initial condition (11.6.6-9)
        
        for j=1:numModes
            % compute mixed state covariance M0 for each filter (11.6.6-10)
            M0(:,:,j)=sum(M(:,:,:,n-1).*reshape(MU(:,j),1,1,[]),3);
            e=x_hat(:,:,n-1)-repmat(X_hat_0(:,j),1,numModes);
            for i = 1:numModes
                M0(:,:,j) = M0(:,:,j) + MU(i,j)*e(:,i)*e(:,i)';
            end
            
            % compute filtered estimate/prediction and updated M for each model
            if j==1 % model 1 (CV mode), vanilla KF
                F = [getF(0,T) zeros(4,1); zeros(1,5)];
                M_pred=F*M0(:,:,1)*F'+[G*Q*G' zeros(4,1); zeros(1,5)];
            elseif j==2 % model 2 (CT mode), extended KF
                F = [getF(X_hat_0(5,2),T) zeros(4,1); zeros(1,4) 1];
                f_x = get_f_x(X_hat_0(:,2),T);
                M_pred=f_x*M0(:,:,2)*f_x'+[G*Q*G' zeros(4,1); zeros(1,4) T^2*Om_var];
            else
                error('Invalid model number.');
            end
            x_hat_pred(:,j,n)=F*X_hat_0(:,j);        % state prediction
            z_hat_pred = H*x_hat_pred(:,j,n);        % output prediction
            S=(H*M_pred*H'+R);                       % S matrix from KF
            S=(S+S')/2;                              % S should be symmetric, but make it so in ill-conditioned cases 
            K=M_pred*H'/S;                           % Kalman gain
            x_hat(:,j,n)=x_hat_pred(:,j,n)+K*(z(:,n,k)-H*x_hat_pred(:,j,n));  % new estimate
            %M(:,:,j,n)=(eye(5)-K*H)*M_pred;         % update covariance
            M(:,:,j,n)=(eye(5)-K*H)*M_pred*(eye(5)-K*H)'+K*R*K';  % same as above... more computationally expensive, but guarantees symmetry when things are ill-conditioned
            Lambda(j) = mvnpdf(z(:,n,k),z_hat_pred,S); % compute likelihood functions (11.6.6-11)
        end
        
        % mixing probability calculation, compute final output state estimate
        Lambda(Lambda<eps)=eps;                           % numerical hack for small Lambdas
        mu(:,n)=(Lambda.*c_bar)/(Lambda'*c_bar);          % update mode probabilities (11.6.6-15)
        x_hat_imm(:,n)=x_hat(:,:,n)*mu(:,n);              % compute combined estimate (11.6.6-17)
        x_hat_pred_imm(:,n)=x_hat_pred(:,:,n)*mu(:,n-1);  % compute combined prediction
        
        %% compute sample mean square error (i.e., actual, not theoretical)
        e=x_hat_imm([1 3],n)-x(:,n,k);               % error between estimate and true state
        e_pred=x_hat_pred_imm([1 3],n)-x(:,n,k);     % error between prediction and true state
        sampleM(:,:,n)=sampleM(:,:,n)+e*e'/numSims;  % sample MSE
        sampleM_pred(:,:,n)=sampleM_pred(:,:,n)+e_pred*e_pred'/numSims;  % sample prediction MSE
        
    end
    
    % report percentage complete to user
    if ismember(k,round(linspace(0,numSims,11)))
        fprintf([num2str(round(k/numSims*100)) '%%...'])
    end
    
end
disp(' '); % newline
IMM_MSE = squeeze(sampleM_pred(1,1,:)+sampleM_pred(2,2,:));  % save resulting (combined x and y) prediction MSE

%% report performance of IMM
disp(['Averaged over ' num2str(numSims) ' realizations with ' num2str(N2-seqLength-1) ' samples each, the mean'])
disp('squared prediction error (x and y coords combined) is as follows:')
disp(' ')
disp(['IMM: ' num2str(mean(IMM_MSE(seqLength+2:end)))])

%% save results
Om_imm=x_hat_imm(5,:)';
Om_ct=squeeze(x_hat(5,2,:));
save(outfile,'IMM_MSE','x_hat_pred_imm','mu','Om_imm','Om_ct')


%% Define F matrix which is a function of Om (turn rate, possibly time-varying) and T (sample interval, a constant)
function F = getF(Om, T)
if Om % Bar-Shalom, (11.7.1-4)
    F = [1 sin(Om*T)/Om 0 -(1-cos(Om*T))/Om; 0 cos(Om*T) 0 -sin(Om*T); 0 (1-cos(Om*T))/Om 1 sin(Om*T)/Om; 0 sin(Om*T) 0 cos(Om*T)];
else % Om=0, not turning
    F = [1 T 0 0; 0 1 0 0; 0 0 1 T; 0 0 0 1];
end
end

%% Define f_x matrix for EKF which is a function of estimated state (x) and T (sample interval, a constant)
function F = get_f_x(x, T)
Om=x(5);
F = eye(5);
if abs(Om)>eps % Bar-Shalom, (11.7.2-4)
    F(1:4,2) = [sin(Om*T)/Om cos(Om*T) (1-cos(Om*T))/Om sin(Om*T)]';
    F(1:4,4) = [-(1-cos(Om*T))/Om -sin(Om*T) sin(Om*T)/Om cos(Om*T)]';
    F(1:4,5) = [cos(Om*T)*T*x(2)/Om-sin(Om*T)*x(2)/Om^2-sin(Om*T)*T*x(4)/Om-(-1+cos(Om*T))*x(4)/Om^2
        -sin(Om*T)*T*x(2)-cos(Om*T)*T*x(4)
        sin(Om*T)*T*x(2)/Om-(1-cos(Om*T))*x(2)/Om^2+cos(Om*T)*T*x(4)/Om-sin(Om*T)*x(4)/Om^2
        cos(Om*T)*T*x(2)-sin(Om*T)*T*x(4)];
else % Om=0, Bar-Shalom, (11.7.2-7)
    F(1,2) = T;
    F(3,4) = T;
    F(1:4,5) = [-T^2/2*x(4) -T*x(4) T^2/2*x(2) T*x(2)]';
end
end
