
from scipy.signal import butter, sosfiltfilt


def bandpass(x, fs, fmin, fmax, order=4):
    sos = butter(order, [fmin, fmax], btype="bandpass", fs=fs, output="sos")

    return sosfiltfilt(sos, x)
