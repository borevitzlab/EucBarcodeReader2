#!/usr/bin/env python3
# External
from docopt import docopt
import exifread
import numpy as np
import PIL
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from tqdm import tqdm
import zbarlight

# Internal
import csv
from functools import partial
import logging
from logging import ERROR, WARNING, INFO, DEBUG
import multiprocessing as mp
import os
import shutil
from sys import stdin, stdout, stderr

def get_logger(level=INFO):
    log = logging.getLogger(__name__)
    log.setLevel(level)
    stderr = logging.StreamHandler()
    stderr.setLevel(DEBUG)
    stderr.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(stderr)
    return log

LOG = get_logger()

def get_args():
    CLI= """
    USAGE:
        barcode-reader.py [options] -o OUTDIR INPUT_IMAGE ...

    OPTIONS:
        -t THREADS      Number of threads [default: 1]
        -o OUTDIR       Output directory (creates subdirectories under here)
        -a              Ask if we can't automatically get some data (NOT IMPLEMENTED)
    """
    opts = docopt(CLI)
    return {"inputs": opts["INPUT_IMAGE"],
            "output_dir": opts["-o"],
            #"ask": opts["-a"],
            "threads": int(opts['-t'])}


def get_qrcode(image):
    x, y = image.size
    # Reduce image size until the barcode scans
    for scalar in list(np.sqrt(np.arange(1.0, 0.01, -0.03))):
        LOG.debug("scalar is: %r", scalar)
        img_scaled = image.resize((int(x*scalar), int(y*scalar)))
        codes = zbarlight.scan_codes('qrcode', img_scaled)
        LOG.debug("got codes: %r", codes)
        if codes is not None:
            if len(codes) == 1:
                return codes[0].decode('utf8')
            elif len(codes) > 1:
                LOG.warn("Image with more than 1 QR code: '%s'", image.filename)
                return None


def get_exif(image):
    exifdata = image._getexif()
    decoded = dict((TAGS.get(key, key), value) for key, value in exifdata.items())
    datetime = decoded['DateTimeOriginal']
    try:
        # GPS EXIF Vomit.
        # {
        #     1: 'N', # latitude ref
        #     2: ((51, 1), (3154, 100), (0, 1)), # latitude, rational degrees, mins, secs
        #     3: 'W', # longitude ref
        #     4: ((0, 1), (755, 100), (0, 1)), # longitude rational degrees, mins, secs
        #     5: 0, # altitude ref: 0 = above sea level, 1 = below sea level
        #     6: (25241, 397), # altitude, expressed as a rational number
        #     7: ((12, 1), (16, 1), (3247, 100)), # UTC timestamp, rational H, M, S
        #     16: 'T', # image direction when captured, T = true, M = magnetic
        #     17: (145423, 418) # image direction in degrees, rational
        # }

        # Latitude
        lat = [float(x) / float(y) for x, y in decoded['GPSInfo'][2]] # pull out latitude
        lat = lat[0] + lat[1] / 60
        if decoded['GPSInfo'][1] == "S": # correction for location relative to equator
            lat *= -1

        # Longitude
        lon = [float(x) / float(y) for x, y in decoded['GPSInfo'][4]] # pull out longditude
        lon = lon[0] + lon[1] / 60
        if decoded['GPSInfo'][3] == "W": # corection for location relative to g'wch
            lon *= -1

        # Elevation
        alt = float(decoded['GPSInfo'][6][0]) / float(decoded['GPSInfo'][6][1])
        gps = (lat,lon,alt)
    except KeyError:
        gps = None
    return datetime, gps


def copy_to(source, destdir):
    from os.path import exists, basename, join, splitext
    destfile = join(destdir, basename(source))
    if not exists(destdir):
        os.makedirs(destdir, exist_ok=True)
    while exists(destfile):
        LOG.warn("Warning: '%s' exists, appending '_2' to name", destfile)
        base, ext = splitext(destfile)
        destfile = base + "_2" + ext
    shutil.copy2(source, destfile)
    LOG.debug("cp %s %s", source, destfile)


def process_image(outdir, f):
    try:
        image = Image.open(f)
    except Exception as exc:
        LOG.error("Couldn't read image '%s'", f)
        LOG.info("ERROR: %s", str(exc))
        copy_to(f, outdir + "/unknown")
        return None

    image_code = get_qrcode(image)
    if not image_code:
        image_code = "unknown"
    copy_to(f, outdir + "/" + image_code)

    datetime, gps = get_exif(image)
    if gps is None:
        gps = ("NA", "NA", "NA")
    return (f, image_code, datetime, *gps)

def main(inputs, output_dir, threads=1):
    # Setup output
    out = output_dir
    if os.path.isdir(out):
        LOG.warn("WARNING: output directory '%s' exists!", out)
    else:
        os.makedirs(out)
    tsv_out = out + "/image_metadata.tsv"
    if not os.path.exists(tsv_out):
        with open(tsv_out, "w") as fh:
            print("image_path", "image_code", "exif_datetime", "exif_latitude",
                  "exif_longitude", "exif_elevation", file=fh, sep="\t")

    if threads > 1:
        pool = mp.Pool(threads)
        map_ = pool.imap
    else:
        map_ = map
    proc_img_with_opts = partial(process_image, out)
    for result in tqdm(map_(proc_img_with_opts, inputs)):
        if result:
            with open(tsv_out, "a")  as fh:
                print(*result, file=fh, sep="\t")

if __name__ == "__main__":
    main(**get_args())
