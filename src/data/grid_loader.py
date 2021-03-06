from __future__ import print_function
import os
import os.path
import torch.utils.data as data
from torchvision import transforms

from os import walk

from video.video import Video
from video.transform.localizeface import LocalizeFace

'''
Grid Dataset:
``dset.GRID(root="dir)``
'''

class GRID(data.Dataset):
    """VOC Classification Dataset Object

    input is image, target is annotation

    Arguments:
        root (string): filepath to VOCdevkit folder.
        image_set (string): imageset to use (eg. 'train', 'val', 'test')
        transform (callable, optional): transformation to perform on the
            input image
        target_transform (callable, optional): transformation to perform on the
            target `annotation`
            (eg: take in caption string, return tensor of word indices)
        dataset_name (string, optional): which dataset to load
            (default: 'VOC2007')
    """

    def __init__(self, root, transform=None, target_transform=None):
        self.root = root
        self.transform = transform
        self.target_transform = target_transform

        self.vid_dir = 'vid'
        self.anno_dir = 'align'
        #self.transform = transform
        #self.target_transform = target_transform
        self.VID_EXT = "mpg"
        self.ANNO_EXT = "align"
        self.ids = []
        self.id_to_user = {}

        # 1 arg is id
        self._annopath = os.path.join(
            self.root, self.anno_dir, '%s.' + self.ANNO_EXT)

        # 1 arg is speaker dir
        # 2 arg is id
        self._vidpath = os.path.join(
            self.root, self.vid_dir, '%s','%s.' + self.VID_EXT )

        # Aid in construction of Ids and video locations,

        video_path = os.path.join(self.root, self.vid_dir)
        for (dirName, subdirList, filenames) in walk(video_path, topdown=False):
            print("Found Vid Dir: %s" % dirName)
            user_dir = os.path.split(dirName)[-1]
            for fname in filenames:
                if not fname.endswith('.' + self.VID_EXT):
                    continue

                id = os.path.splitext(fname)[0]
                self.id_to_user[id] = user_dir

        print("Map of Users(%s)" % len(self.id_to_user))

        self.ids = list(self.id_to_user.keys())


    def __getitem__(self, index):
        data_id = self.ids[index]

        # Needed to find Video Directory
        user = self.id_to_user[data_id]

        vid_path = self._vidpath % (user, data_id)
        anno_path = self._annopath % str(data_id)

        print("loading video: %s" % vid_path )
        print("loading aligns: %s" % anno_path )

        # each frame is (288, 360, 3) by default
        video = Video(vid_path, anno_path, self.transform, self.target_transform)

        #TODO: If we want Transforms for videos
        # Ideas are to mirror frames and randomly select video for data augmentation
        # Randomly selecting video would be easy, just randomize the ids list
        # For mirroring, we can
        # Set transforms in video and have to it in getItem!!
        '''
        if self.transform is not None:
            img = self.transform(img)

        if self.target_transform is not None:
            target = self.target_transform(target)
        '''

        return video

    def __len__(self):
        return len(self.ids)


# def video_collate(batch):
#     """Custom collate fn for dealing with batches of images that have a different
#     number of associated object annotations (bounding boxes).
#
#     Arguments:
#         batch: (tuple) A tuple of tensor images and lists of annotations
#
#     Return:
#         A tuple containing:
#             1) (tensor) batch of images stacked on their 0 dim
#             2) (list of tensors) annotations for a given image are stacked on 0 dim
#     """
#
#     data = [item[0] for item in batch]
#     target = [item[1] for item in batch]
#     target = torch.LongTensor(target)
#
#     return [data,target]

def main():
    #frame_transforms = transforms.Compose([LocalizeFace()])
    # normMean = [0.49139968, 0.48215827, 0.44653124]
    #normStd = [0.24703233, 0.24348505, 0.26158768]
    #normTransform = transforms.Normalize(normMean, normStd)

    frame_transforms = transforms.Compose([
        LocalizeFace(height=256,width=256),
        transforms.ToTensor()#,
        #normTransform
    ])

    data_path = '/home/jake/classes/cs703/Project/data/grid/'
    loader = GRID(data_path, transform=frame_transforms)

    count = 0

    for video in loader:
        # Only testing
        if count > 1:
            return
        count += 1
        for idx, (frame, word) in enumerate(video):
            print("Word: %s \nFrame: %s" % (word, frame))
            #width, height = frame.size
            #print("Frame size: w=", width, ", h=", height)
            #frame.show()
            # Only testing
            break

    #cv2.destroyAllWindows()


if __name__ == '__main__':

    main()