#  Copyright (c) 2019 PaddlePaddle Authors. All Rights Reserve.
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

import argparse
import logging
import numpy as np
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '5'
import paddle
import paddle.fluid as fluid
import reader
import network

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fluid")
logger.setLevel(logging.INFO)


def parse_args():
    parser = argparse.ArgumentParser(description="PaddlePaddle DIN example")
    parser.add_argument(
        '--model_path', type=str, default='./saved_model/', help="path of model parameters")
    parser.add_argument(
        '--test_path', type=str, default='./data/diginetica/test.txt', help='dir of test file')
    parser.add_argument(
        '--config_path', type=str, default='./data/diginetica/config.txt', help='dir of config')
    parser.add_argument(
        '--use_cuda', type=int, default=1, help='whether to use gpu')
    parser.add_argument(
        '--batch_size', type=int, default=100, help='input batch size')
    parser.add_argument(
        '--start_index', type=int, default='0', help='start index')
    parser.add_argument(
        '--last_index', type=int, default='10', help='end index')
    parser.add_argument(
        '--hidden_size', type=int, default=100, help='hidden state size')
    parser.add_argument(
        '--step', type=int, default=1, help='gnn propogation steps')
    return parser.parse_args()


def infer_wrong(args):
    batch_size = args.batch_size
    items_num = reader.read_config(args.config_path)
    test_data = reader.Data(args.test_path, False)
    place = fluid.CUDAPlace(0) if args.use_cuda else fluid.CPUPlace()
    exe = fluid.Executor(place)
    loss, acc, py_reader, feed_datas = network.network(items_num, args.hidden_size, args.step, batch_size)
    exe.run(fluid.default_startup_program())
    infer_program = fluid.default_main_program().clone(for_test=True)

    for epoch_num in range(args.start_index, args.last_index + 1):
        model_path = os.path.join(args.model_path,  "epoch_" + str(epoch_num))
        try:
            if not os.path.exists(model_path):
                raise ValueError()
            fluid.io.load_persistables(executor=exe, dirname=model_path,
                    main_program=infer_program)

            loss_sum = 0.0
            acc_sum = 0.0
            count = 0
            py_reader.set_sample_list_generator(test_data.reader(batch_size, batch_size*20, False))
            py_reader.start()
            try:
                while True:
                    res = exe.run(infer_program,
                                  fetch_list=[loss.name, acc.name], use_program_cache=True)
                    loss_sum += res[0]
                    acc_sum += res[1]
                    count += 1
            except fluid.core.EOFException:
                py_reader.reset()
            logger.info("TEST --> loss: %.4lf, Recall@20: %.4lf" %
                        (loss_sum / count, acc_sum / count))
        except ValueError as e:
            logger.info("TEST --> error: there is no model in " + model_path)

def infer(args):
    batch_size = args.batch_size
    items_num = reader.read_config(args.config_path)
    test_data = reader.Data(args.test_path, False)
    place = fluid.CUDAPlace(0) if args.use_cuda else fluid.CPUPlace()
    exe = fluid.Executor(place)

    loss, acc, py_reader, feed_datas, logits = network.network(items_num, args.hidden_size, args.step, args.batch_size)
    exe.run(fluid.default_startup_program())
    
    [infer_program, feeded_var_names, target_var] = fluid.io.load_inference_model(dirname=args.model_path, executor=exe)
    
    feed_list = [e.name for e in feed_datas]
    print(feed_list, type(target_var[0]), type(logits))

    infer_reader = test_data.reader(batch_size, batch_size*20, False)
    feeder = fluid.DataFeeder(place=place, feed_list=feed_list)
    for iter, data in enumerate(infer_reader()):
        
        res = exe.run(infer_program, feed=feeder.feed(data), fetch_list=[logits])
        #logits = res
        #print('session:', data, 'label:',np.argmax(logits))
        print("@@@, " , res)
        print("!!!,", logits)
        if iter == 0:
            break
        

if __name__ == "__main__":
    args = parse_args()
    infer(args)
