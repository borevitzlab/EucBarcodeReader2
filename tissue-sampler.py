#!/usr/bin/env python3
from PIL import Image
import zbarlight as zbar
import subprocess as sp
import readline
import io
import os
import os.path as op
import csv


def ask_yesno(prompt, default=True):
    if default:
        prompt += " [Y/n] "
    else:
        prompt += " [y/N] "
    resp = input(prompt)
    if not resp:
        return default
    elif resp.lower()[0] == 'y':
        return True
    else:
        return False


def ask_default(prompt, default="", dtype=str):
    prompt += " [%s] " % default
    resp = input(prompt)
    if not resp:
        return dtype(default)
    else:
        return dtype(resp)


def qrdecode(image):
    code = zbar.scan_codes('qrcode', image)
    if isinstance(code, list):
        code = code[0]
    if isinstance(code, bytes):
        return code.decode('utf-8')
    else:
        return code


def capture_image():
    """Captures images from camera using gphoto CLI"""
    capture_cmd = "gphoto2 --capture-image-and-download --stdout".split()

    proc = sp.Popen(capture_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    while True:
        try:
            out, err = proc.communicate(timeout=20)
            break
        except sp.TimeoutExpired:
            if ask_yesno("Image capture is taking ages. Kill capture?"):
                proc.kill()
    if proc.returncode != 0:
        if ask_yesno("Image capture failed. Retry?"):
            return capture_image()
        else:
            return None
    return out

# for debugging, replace above with:
#def capture_image():
#    with open("data/test-image.jpg", "rb") as fh:
#        return fh.read()


def show_image(image):
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.imshow(np.asarray(image))
    plt.show()


N2W = ['{}{:02d}'.format(a, i) for i in range(1,13) for a in "ABCDEFGH"]
W2N = {w: i for i, w in enumerate(N2W)}


class Capturer(object):

    def __init__(self, outdir):
        os.makedirs(outdir, exist_ok=True)
        self.outdir = outdir
        self.sample_csv = outdir + "/samples.csv"
        self.samples = set()
        self.platewell = set()
        self.plate = ""
        self.well = -1
        if not op.exists(self.sample_csv):
            with open(self.sample_csv, "w") as fh:
                print("sample_id", "plate", "well", 'has_seed', sep=',', file=fh)
        else:
            # Read list of existing sample & plate/well from CSV
            for rec in csv.DictReader(open(self.sample_csv)):
                print(rec)
                self.samples.add(rec["sample_id"])
                self.platewell.add((rec["plate"], rec["well"]))
            # set to last record
            self.plate = rec["plate"]
            self.well = W2N.get(rec["well"], -1)
            print("Read", len(self.samples), "existing samples from output directory")

    def capture_sample(self):
        images = []
        sample_id = None
        has_seed = False
        try:
            while True:
                img_jpg = capture_image()
                images.append(img_jpg)
                img = Image.open(io.BytesIO(img_jpg))
                if ask_yesno("Show image?", False):
                    show_image(img)
                while sample_id is None or sample_id == "":
                    sid = qrdecode(img)
                    if sid is None:
                        sid = ""
                    sample_id = ask_default("Sample name is", sid)
                    while sample_id in self.samples:
                        print("ERROR: duplicate sample ID. Something's fishy")
                        sample_id = ask_default("Sample name is", sid)
                self.samples.add(sample_id)
                if not ask_yesno("Capture another image?", False):
                    break
            plate = None
            well = None
            while True:
                plate = ask_default("Which plate?", default=self.plate)
                # Increment well number, ask to confirm
                while True:
                    well = N2W[(self.well + 1) % 96]
                    well = ask_default("Which well?", default=well)
                    if well not in W2N:
                        print("Invalid well:", well, "(must be like A01)")
                    else:
                        break

                platewell = (plate, well)
                if not platewell in self.platewell:
                    self.plate = plate
                    self.well = W2N[well]
                    self.platewell.add(platewell)
                    break
                else:
                    print("ERROR: this plate and well used already. Something's very fishy")
            has_seed = ask_yesno("Does this sample have seed?")
        except KeyboardInterrupt:
            pass
        if sample_id is None or sample_id == "":
            return
        # Make image dir
        imagedir = op.join(self.outdir, sample_id)
        os.makedirs(imagedir, exist_ok=False)
        # Write images
        for i, jpgbytes in enumerate(images):
            fn = op.join(imagedir, "{:02d}.jpg".format(i))
            with open(fn, "wb") as fh:
                fh.write(jpgbytes)
        # Append to sample CSV
        seed = "Yes" if has_seed else "No"
        with open(self.sample_csv, "a") as fh:
            print(sample_id, self.plate, N2W[self.well], seed, sep=",", file=fh)

    def main(self):
        while True:
            try:
                print("\nPress enter to start sample capture, or 'exit' to exit...  ", end="")
                res = input().strip()
                if res == "":
                    self.capture_sample()
                elif res.lower() == "exit":
                    break
            except (KeyboardInterrupt, EOFError):
                break


if __name__ == "__main__":
    DOC = """
    USAGE:
        tissue-sampler.py OUTDIR

    The output directory will contain a directory of images for each sample, as
    well as a CSV of all samples and their plate coordinates.
    """
    from docopt import docopt
    args = docopt(DOC)
    Capturer(args['OUTDIR']).main()
