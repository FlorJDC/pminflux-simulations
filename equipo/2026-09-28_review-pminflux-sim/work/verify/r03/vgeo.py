# -*- coding: utf-8 -*-
"""Verifier r03: general-geometry forward models (own code, no pminflux_sim import)."""
import os, sys, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "r02"))
from mysim import my_C  # noqa

T, K, FWHM = 50.0, 4, 360.0
POS_MEAS = np.array([[0.0399, 0.1078], [-44.1278, -26.6938], [45.2029, -25.7607], [-4.8180, 50.7680]])
POWERS = np.array([21.02, 16.65, 22.96, 22.86])
POSITIONS = [(-5.07, -7.56), (6.31, -4.87), (12.73, 8.14), (-14.22, 3.37), (2.91, 17.58)]


def ring(L, phi=0.0):
    ang = 2 * np.pi * np.arange(1, 4) / 3 + phi
    return np.vstack([[0.0, 0.0], np.c_[L / 2 * np.cos(ang), L / 2 * np.sin(ang)]])


def naive_geom(pm):
    rr = pm[1:] - pm[0]
    L = 2 * np.mean(np.hypot(rr[:, 0], rr[:, 1]))
    th = np.arctan2(rr[:, 1], rr[:, 0]) - 2 * np.pi * np.arange(1, 4) / 3
    phi = float(np.angle(np.mean(np.exp(1j * th))))
    return ring(L, phi), L, phi


def q_of(x, y, pos, pw):
    x = np.asarray(x, float)[..., None]; y = np.asarray(y, float)[..., None]
    u = 4 * np.log(2) * ((x - pos[:, 0]) ** 2 + (y - pos[:, 1]) ** 2) / FWHM ** 2
    lam = u * np.exp(-u) * pw
    return lam / lam.sum(-1, keepdims=True)


def model_mix(pos, pw, C, b, sbr):
    beta = 1.0 / (sbr + 1.0)
    def p(x, y):
        q = q_of(x, y, pos, pw)
        e = (1 - beta) * q.dot(C.T) + beta * b / T
        return e / e.sum(-1, keepdims=True)
    return p


def model_legacy(pos, pw, sbr):
    def p(x, y):
        q = q_of(x, y, pos, pw)
        return sbr / (sbr + 1) * q + 1 / (sbr + 1) / K
    return p


def captured(C, b, sbr):
    beta = 1.0 / (sbr + 1.0)
    return (1 - beta) * C.sum(0).mean() + beta * K * b / T
