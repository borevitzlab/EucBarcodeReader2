#!/usr/bin/env python3
from PIL import Image
import zbarlight as zbar
import subprocess as sp
import readline
import io
import os
import os.path as op


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
    return out


def show_image(image):
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.imshow(np.asarray(image))
    plt.show()



class Capturer(object):
    """Captures images from camera using gphoto CLI"""

    def __init__(self, imagedir, samplecsv):
        os.makedirs(imagedir, exist_ok=False)
        self.imagedir = imagedir
        self.sample_csv = samplecsv
        with open(self.sample_csv, "w") as fh:
            print("sample_id", "tube_id", sep=',', file=fh)
        self.well = 0

    def capture_sample(self):
        images = []
        sample_id = None
        tube_id = None
        try:
            while True:
                img_jpg = capture_image()
                images.append(img_jpg)
                img = Image.open(io.BytesIO(img_jpg))
                if ask_yesno("Show image?"):
                    show_image(img)
                if sample_id is None:
                    sid = qrdecode(img)
                    if sid is None:
                        sid = ""
                    sample_id = ask_default("Sample name is", sid)
                if not ask_yesno("Capture another image?"):
                    break
            tube_id = ask_default("What's the tube label?", default=sample_id)
        except KeyboardInterrupt:
            pass
        finally:
            if sample_id is None or sample_id == "":
                return
            # Make image dir
            imagedir = op.join(self.imagedir, sample_id)
            os.makedirs(imagedir, exist_ok=False)
            # Write images
            for i, jpgbytes in enumerate(images):
                fn = op.join(imagedir, "{:02d}.jpg".format(i))
                with open(fn, "wb") as fh:
                    fh.write(jpgbytes)
            # Append to sample CSV
            with open(self.sample_csv, "a") as fh:
                print(sample_id, tube_id, sep=",", file=fh)

    def main(self):
        while True:
            try:
                print("Press enter to start sample capture, or 'exit' to exit..", end="")
                res = input()
                if res.strip().lower() == "exit":
                    break
            except (KeyboardInterrupt, EOFError):
                break
            self.capture_sample()


if __name__ == "__main__":
    DOC = """
    USAGE:
        tissue-sampler.py -c CSV -d OUTDIR

    OPTIONS:
        -d OUTDIR   Image output directory (base of per-sample image directories).
        -c CSV      Sample -> Tube ID mapping CSV filename (will be overwritten).
    """
    from docopt import docopt
    args = docopt(DOC)
    samplecsv = args['-c']
    outdir = args['-d']

    c = Capturer(outdir, samplecsv)
    c.main()
