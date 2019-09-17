N=1e2;
mu1=0.5;
sig1=0.2;
mu2=0.4;
sig2=0.2;

% generate initial random numbers
f1=(randn(N,1))*sqrt(sig1)+mu1;
f2=(randn(N,1))*sqrt(sig2)+mu2;

% resample among those that are stable
idx=abs((f1.^2 + 4*f2).^(1/2)/2 - f1/2)<1 & abs(f1/2 + (f1.^2 + 4*f2).^(1/2)/2)<1;

% compute mean of stable values
disp('Mean of stable f1 and f2 is:')
mean([f1(idx) f2(idx)])

