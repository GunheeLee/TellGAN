from __future__ import print_function

import time
import numpy as np
import cv2
import dlib


import itertools
from options.train_options import TrainOptions
from data import CreateDataLoader
from models.networks import NextFrameConvLSTM
from util.visualizer import Visualizer
from data.video.transform.localizeface import LocalizeFace
from data.grid_loader import GRID
import torch
import torch.nn as nn
from torchvision import transforms
import torch.optim as optim
from torch.optim import lr_scheduler
from torch.autograd import Variable
from PIL import Image
import skvideo.io

class OpticalFlow(object):
    def __init__(self, feature_model=None):
        self.feature_model = feature_model
        self.face_detector = dlib.get_frontal_face_detector()
        self.feature_detector = dlib.shape_predictor(self.feature_model)

        # Parameters for lucas kanade optical flow
        self.lk_params = dict(winSize=(15, 15),
                         maxLevel=2,
                         criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

    def run(self, pil0, pil1, features0=None):
        #mat0 = self.pilToMat(pil0)
        gray0 = cv2.cvtColor(pil0, cv2.COLOR_BGR2GRAY)
        #mat1 = self.pilToMat(pil1)
        gray1 = cv2.cvtColor(pil1, cv2.COLOR_BGR2GRAY)

        if features0 is None:
            features0 = self.getFeaturePoints(gray0)

        features1, features0 = self.getFlow(gray0, gray1, features0)

        mask = self.create_mask(gray1, features1)

        return features1.reshape(-1,1,2), self.matToPil(mask)

    def getInit(self, pil0):
        #gray0 = cv2.cvtColor(self.pilToMat(pil0), cv2.COLOR_BGR2GRAY)
        gray0 = cv2.cvtColor(pil0, cv2.COLOR_BGR2GRAY)
        features0 = self.getFeaturePoints(gray0)

        mask = self.create_mask(gray0, features0)
        return features0, self.matToPil(mask)


    def getFlow(self, old_gray, frame_gray, features0):
        features1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, features0,
                                                      None, ** self.lk_params)
        # Select good points
        good_new = features1[st == 1]
        good_old = features0[st == 1]

        return good_new, good_old

    def create_mask(self, img, features):

        features = np.copy(features).astype(np.int)
        mask = np.zeros_like(img)
        mask[features[:,:,1], features[:,:,0]] = 255

        return mask


    def getFeaturePoints(self, img_grey):
        faces = self.face_detector(img_grey, 1)

        for k, rect in enumerate(faces):
            # print("k: ", k)
            # print("rect: ", rect)
            # shape = self.predictor(img_gray, rect)
            features = self.feature_detector(img_grey, rect)
            break

        feat_points = np.asfarray([])
        for i, part in enumerate(features.parts()):
            fpoint = np.asfarray([part.x, part.y])
            # filter if index values larger than image
            if (fpoint < 0).any() or fpoint[0] >= img_grey.shape[1] or fpoint[1] >= img_grey.shape[0]:
                print("ignoring point: {} | imgsize: {}".format(fpoint,img_grey.shape))
                continue
            if i is 0:
                feat_points = fpoint
            else:
                feat_points = np.vstack((feat_points, fpoint))
        feat_points = np.expand_dims(feat_points, axis=1)



        # print("face_points_shape: ", feat_points.shape)
        # print("feat_points: ", feat_points)
        return feat_points.astype(np.float32)

    def matToPil(self, mat_img):
        return Image.fromarray(mat_img)

    def pilToMat(self, pil_img):
        pil_image = pil_img.convert('RGB')
        open_cv_image = np.array(pil_image)
        # Convert RGB to BGR
        return open_cv_image  # [:, :, ::-1].copy()

def create_video(vid_path, vid_idx, save_freq):
    if vid_idx % save_freq != 0:
        return None

    return skvideo.io.FFmpegWriter(vid_path)

if __name__ == '__main__':
    dataroot = "/home/jake/classes/cs703/Project/data/grid/"

    face_size=(288, 360)

    face_predictor_path = '/home/jake/classes/cs703/Project/dev/TellGAN/src/assests/predictors/shape_predictor_68_face_landmarks.dat'

    toTensor = transforms.ToTensor()
    frame_transforms = transforms.Compose([
        #LocalizeFace(height=face_size,width=face_size),
        #toTensor#,
        #normTransform
    ])

    dataset = GRID(dataroot, transform=frame_transforms)
    dataset_size = len(dataset)
    print('#training images = %d' % dataset_size)

    model = NextFrameConvLSTM(input_size=face_size,input_dim=2,
                              num_layers=3,hidden_dim=[2,3,1],
                              kernel_size=(3,3), batch_first=True)
    model.cuda()

    opticalFlow = OpticalFlow(face_predictor_path)
    embeds = nn.Embedding(100, 1)  # 100 words in vocab,  dimensional embeddings
    word_to_ix = {}

    crit = nn.MSELoss()  # nn.BCEWithLogitsLoss() #GANLoss()
    crit.cuda()
    optimizer = optim.Adam(itertools.chain(model.parameters()))
    scheduler = lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

    total_steps = 0

    vid_path = "pred_mask_{}.mp4"

    for epoch in range(0, 100):

        scheduler.step()
        epoch_start_time = time.time()
        iter_data_time = time.time()
        epoch_iter = 0

        for vid_idx, video in enumerate(dataset):
            iter_start_time = time.time()
            #if total_steps % opt.print_freq == 0:
            #    t_data = iter_start_time - iter_data_time

            #visualizer.reset()
            #total_steps += opt.batchSize
            #epoch_iter += opt.batchSize

            init_tensor=True
            prev_img_seq = None
            word_seq = None
            vid_loss = []
            vidWriter = create_video(vid_path=vid_path.format(vid_idx), vid_idx=vid_idx, save_freq=20)

            # frame is a tuple (frame_img, frame_word)
            for frame_idx, frame in enumerate(video):
                optimizer.zero_grad()
                (img, trans) = frame
                imgT = toTensor(img)

                #if imgT.size(1) is not face_size[0] or imgT.size(2) is not face_size[1] or trans is None:
                if trans is None:
                    print("Incomplete Frame: {0} Size: {1} Word: {2}".format(frame_idx, imgT.size(), trans))
                    prev_img_seq=None
                    word_seq=None
                    init_tensor=True
                    continue

                if trans not in word_to_ix:
                    word_to_ix[trans] = len(word_to_ix)

                lookup_tensor = torch.LongTensor([word_to_ix[trans]])
                trans_embed = embeds(Variable(lookup_tensor))
                transT = trans_embed.repeat(imgT.size(1),imgT.size(2)).unsqueeze(0)

                #np_img = (img.permute(1,2,0).data.cpu().numpy()*255).astype(np.uint8)
                feat0, mask = opticalFlow.getInit(opticalFlow.pilToMat(img))
                #OpticalFlow.matToPil(mask).show()
                maskT = Variable(toTensor(mask))

                # INitialize the input with ground trouth only
                if (init_tensor == True):
                    prev_img_seq = maskT.unsqueeze(0)
                    init_tensor = False
                    if vidWriter is not None:
                        vidWriter.writeFrame(np.concatenate((mask, mask), axis=1))
                    continue

                if word_seq is not None:
                    word_seq = torch.cat((word_seq, transT.unsqueeze(0)), 0)
                else:
                    word_seq = transT.unsqueeze(0)

                #Concat previous image and current word, add batch dim
                input = torch.cat((prev_img_seq, word_seq), 1).cuda()

                pred_maskT = model(input.detach())

                if vidWriter is not None:
                    pred_mask = (pred_maskT.permute(1,2,0).data.cpu().numpy()*255).astype(np.uint8)
                    pil_pred_mask = opticalFlow.matToPil(np.squeeze(pred_mask, axis=2))
                    vidWriter.writeFrame(np.concatenate((mask, pil_pred_mask), axis=1))

                prev_img_seq = torch.cat((prev_img_seq, maskT.unsqueeze(0)), 0)

                loss = crit(pred_maskT, maskT.cuda())

                vid_loss.append(loss.data.cpu().numpy())

                loss.backward()
                optimizer.step()

                if frame_idx%100 == 0:
                    init_tensor=True
                    prev_img_seq=None
                    word_seq=None

            if vidWriter is not None:
                vidWriter.close()

            avg_loss = sum(vid_loss) / len(vid_loss)
            print("ep: {0}, video: {1}, Loss: {2}".format(epoch, vid_idx, avg_loss))
            print("===========================")
