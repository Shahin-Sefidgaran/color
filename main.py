
import subprocess
import subprocess
Quellpfad = r"C:/Program Files (x86)/IntelSWTools/openvino_2020.2.117/bin"
Quelldatei = r"/setupvars.bat"
Quelle = Quellpfad + Quelldatei
print(Quelle)
subprocess.call(Quelle)
#subprocess.call([r'C:/Program Files (x86)/IntelSWTools/openvino_2020.2.117/bin/setupvars.bat'])
from openvino.inference_engine import IENetwork, IECore
import cv2 as cv
import numpy as np
import os
from argparse import ArgumentParser, SUPPRESS
import logging as log
import sys


def build_arg():
    parser = ArgumentParser(add_help=False)
    in_args = parser.add_argument_group('Options')
    in_args.add_argument('-h', '--help', action='help', default=SUPPRESS, help='Help with the script.')
    in_args.add_argument("-m", "--model", help="Required. Path to .xml file with pre-trained model.",
                         required=True, type=str)
    in_args.add_argument("--coeffs", help="Required. Path to .npy file with color coefficients.",
                         required=True, type=str)
    in_args.add_argument("-d", "--device",
                         help="Optional. Specify target device for infer: CPU, GPU, FPGA, HDDL or MYRIAD. "
                              "Default: CPU",
                         default="CPU", type=str)
    in_args.add_argument('-i', "--input",
                         help='Required. Input to process.',
                         required=True, type=str, metavar='"<path>"')
    in_args.add_argument("--no_show", help="Optional. Disable display of results on screen.",
                         action='store_true', default=False)
    in_args.add_argument("-v", "--verbose", help="Optional. Enable display of processing logs on screen.",
                         action='store_true', default=False)
    return parser


if __name__ == '__main__':
    args = build_arg().parse_args()
    model_path = os.path.splitext(args.model)[0]
    weights_bin = model_path + ".bin"
    coeffs = args.coeffs

    # mean is stored in the source caffe model and passed to IR
    log.basicConfig(format="[ %(levelname)s ] %(message)s",
                    level=log.INFO if not args.verbose else log.DEBUG, stream=sys.stdout)

    log.debug("Load network")
    load_net = IENetwork(model=args.model, weights=weights_bin)
    load_net.batch_size = 1
    exec_net = IECore().load_network(network=load_net, device_name=args.device)

    assert len(load_net.inputs) == 1, "Expected number of inputs is equal 1"
    input_blob = next(iter(load_net.inputs))
    input_shape = load_net.inputs[input_blob].shape
    assert input_shape[1] == 1, "Expected model input shape with 1 channel"

    assert len(load_net.outputs) == 1, "Expected number of outputs is equal 1"
    output_blob = next(iter(load_net.outputs))
    output_shape = load_net.outputs[output_blob].shape
    assert output_shape == [1, 313, 56, 56], "Shape of outputs does not match network shape outputs"

    _, _, h_in, w_in = input_shape

    try:
        input_source = int(args.input)
    except ValueError:
        input_source = args.input

    cap = cv.VideoCapture(input_source)
    if not cap.isOpened():
        assert "{} not exist".format(input_source)

    color_coeff = np.load(coeffs).astype(np.float32)
    assert color_coeff.shape == (313, 2), "Current shape of color coefficients does not match required shape"

    # while True:
    log.debug("#############################")
    #hasFrame, original_frame = cap.read()
    #if not hasFrame:
        #break
    img = cv.imread(args.input)
    #(h_orig, w_orig) = original_frame.shape[:2]
    (h_orig, w_orig) = img.shape[:2]
    log.debug("Preprocessing frame")
    if img.shape[2] > 1:
        frame = cv.cvtColor(cv.cvtColor(img, cv.COLOR_BGR2GRAY), cv.COLOR_GRAY2RGB) #change to rgb dar har sorat
    else:
        frame = cv.cvtColor(img, cv.COLOR_GRAY2RGB)

    img_rgb = frame.astype(np.float32) / 255
    img_lab = cv.cvtColor(img_rgb, cv.COLOR_RGB2Lab)
    img_l_rs = cv.resize(img_lab.copy(), (w_in, h_in))[:, :, 0]

    log.debug("Network inference")
    res = exec_net.infer(inputs={input_blob: [img_l_rs]})

    update_res = (res[output_blob] * color_coeff.transpose()[:, :, np.newaxis, np.newaxis]).sum(1)

    log.debug("Get results")
    out = update_res.transpose((1, 2, 0))
    out = cv.resize(out, (w_orig, h_orig))
    img_lab_out = np.concatenate((img_lab[:, :, 0][:, :, np.newaxis], out), axis=2)
    img_bgr_out = np.clip(cv.cvtColor(img_lab_out, cv.COLOR_Lab2BGR), 0, 1)

    if not args.no_show:
        log.debug("Show results")
        imshowSize = (640, 480)
        original_image = cv.resize(img, imshowSize)
        grayscale_image = cv.resize(frame, imshowSize)
        colorize_image = (cv.resize(img_bgr_out, imshowSize) * 255).astype(np.uint8)
        lab_image = (cv.resize(img_lab_out, imshowSize)).astype(np.uint8)

        original_image = cv.putText(original_image, 'Original', (25, 50),
                                    cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv.LINE_AA)
        grayscale_image = cv.putText(grayscale_image, 'Grayscale', (25, 50),
                                    cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv.LINE_AA)
        colorize_image = cv.putText(colorize_image, 'Colorize', (25, 50),
                                    cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv.LINE_AA)
        lab_image = cv.putText(lab_image, 'LAB interpetation', (25, 50),
                               cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv.LINE_AA)

        ir_image = [cv.hconcat([original_image, grayscale_image]),
                    cv.hconcat([lab_image, colorize_image])]
        final_image = cv.vconcat(ir_image)
        cv.imshow('Colorization Demo', final_image)
        cv.waitKey(0) # waits until a key is pressed
        cv.destroyAllWindows() # destroys the window showing image
            #if not cv.waitKey(1) < 0:
                #break
