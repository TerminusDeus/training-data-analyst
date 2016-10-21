#!/usr/bin/env python

"""
Copyright Google Inc. 2016
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import apache_beam as beam
import numpy as np
import argparse
import datetime
import ndvi

class SceneInfo:
   def __init__ (self, line):
      try:
        self.SCENE_ID, self.SPACECRAFT_ID, self.SENSOR_ID, self.DATE_ACQUIRED, self.COLLECTION_NUMBER, self.COLLECTION_CATEGORY,self.DATA_TYPE, self.WRS_PATH, self.WRS_ROW, self.CLOUD_COVER, self.NORTH_LAT, self.SOUTH_LAT, self.WEST_LON, self.EAST_LON, self.TOTAL_SIZE, self.BASE_URL = line.split(',')

        self.DATE_ACQUIRED = datetime.datetime.strptime(self.DATE_ACQUIRED, '%Y-%m-%d')
        self.NORTH_LAT = float(self.NORTH_LAT)
        self.SOUTH_LAT = float(self.SOUTH_LAT)
        self.WEST_LON = float(self.WEST_LON)
        self.EAST_LON = float(self.EAST_LON)
        self.CLOUD_COVER = float(self.CLOUD_COVER)
      except:
        print "WARNING! format error on {", line, "}"        

   def contains(self, lat, lon):
      return (lat > self.SOUTH_LAT) and (lat < self.NORTH_LAT) and (lon > self.WEST_LON) and (lon < self.EAST_LON)

   def distanceFrom(self, lat, lon):
      return np.sqrt(np.square(lat - (self.SOUTH_LAT + self.NORTH_LAT)/2) + 
                     np.square(lon - (self.WEST_LON + self.EAST_LON)/2))

   def timeDiff(self, date):
      return (self.DATE_ACQUIRED - date).days


def filterScenes(line, lat, lon):
   scene = SceneInfo(line)
   if scene.contains(lat, lon) and scene.DATE_ACQUIRED.day > 10 and scene.DATE_ACQUIRED.day < 20:
      yrmon = '{0}-{1}'.format(scene.DATE_ACQUIRED.year, scene.DATE_ACQUIRED.month)
      yield (yrmon, scene)

def clearest(scenes):
   if scenes:
      return min(scenes, key=lambda s: s.CLOUD_COVER)
   else:
      return None

def run():
   parser = argparse.ArgumentParser(description='Compute monthly NDVI')
   parser.add_argument('--index_file', default='2015index.txt.gz', help='default=2015index.txt.gz  Use gs://gcp-public-data-landsat/index.csv.gz to process full dataset')
   parser.add_argument('--output_file', default='output.txt', help='default=output.txt Supply a location on GCS when running on cloud')
   parser.add_argument('--output_dir', required=True, help='Where should the ndvi images be stored? Supply a GCS location when running on cloud')
   known_args, pipeline_args = parser.parse_known_args()
 
   p = beam.Pipeline(argv=pipeline_args)
   index_file = known_args.index_file
   output_file = known_args.output_file
   output_dir = known_args.output_dir

   # Madagascar
   lat =  -19
   lon =   47

   # Read the index file and find the best look
   scenes = (p
      | 'read_index' >> beam.Read(beam.io.TextFileSource(index_file))
      | 'filter_scenes' >> beam.FlatMap(lambda line: filterScenes(line, lat, lon) )
      | 'least_cloudy' >> beam.CombinePerKey(clearest)
   )

   # write out info about scene
   scenes | beam.Map(lambda (yrmon, scene): scene.__dict__) | 'scene_info' >> beam.io.textio.WriteToText(output_file)

   # compute ndvi on scene
   scenes | 'compute_ndvi' >> beam.Map(lambda (yrmon, scene): ndvi.computeNdvi(scene.BASE_URL, output_dir))

   p.run()

if __name__ == '__main__':
   run()
