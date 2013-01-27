# -*- coding: utf-8 -*-
import os
import csv

from django.core.management.base import BaseCommand
from geo.models import *
from utils.http import HttpFetcher
from django.conf import settings
from django import db
from django.contrib.gis.gdal import DataSource, SpatialReference, CoordTransform
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point

MUNI_URL = "http://tilastokeskus.fi/meta/luokitukset/kunta/001-2013/tekstitiedosto.txt"

class Command(BaseCommand):
    help = "Manage stats app"

    def import_municipalities(self):
        s = self.http.open_url(MUNI_URL, "muni")
        # strip first 4 lines of header and any blank/empty lines at EOF
        count = 0
        for line in s.rstrip().split('\n')[4:]:
            dec_line = line.decode('iso8859-1').rstrip().split('\t')
            (muni_id, muni_name) = dec_line
            muni_id = int(muni_id)
            muni_name = muni_name.split(' - ')[0]

            try:
                muni = Municipality.objects.get(id=muni_id)
            except:
                muni = Municipality(id=muni_id, name=muni_name)
                muni.save()
                count += 1
        print "%d municipalities added." % count

    def import_addresses(self):
        f = open(os.path.join(self.data_path, 'pks_osoite.csv'))
        reader = csv.reader(f, delimiter=',')
        reader.next()
        muni_list = Municipality.objects.all()
        muni_dict = {}
        for muni in muni_list:
            muni_dict[muni.name] = muni
        for idx, row in enumerate(reader):
            street = row[0]
            num = int(row[1])
            num2 = row[2]
            letter = row[3]
            coord_n = int(row[8])
            coord_e = int(row[9])
            muni_name = row[10]
            row_type = int(row[-1])
            if row_type != 1:
                continue
            id_s = "%s %d" % (street, num)
            if id_s == 'Eliel Saarisen tie 4':
                muni_name = 'Helsinki'
            muni = muni_dict[muni_name]
            args = dict(municipality=muni, street=street, number=num, letter=letter)
            try:
                addr = Address.objects.get(**args)
            except Address.DoesNotExist:
                addr = Address(**args)
            # 3879
            to_wgs84 = CoordTransform(SpatialReference('3879'), SpatialReference('WGS84'))
            pnt = Point(coord_e, coord_n, srid=3879)
            pnt.transform(to_wgs84)
            #print "%s: %s %d%s N%d E%d (%f,%f)" % (muni_name, street, num, letter, coord_n, coord_e, pnt.y, pnt.x)
            if idx > 0 and idx % 1000 == 0:
                print "%d addresses processed" % idx
                # Reset DB query store to free up memory
                db.reset_queries()
            addr.location = pnt
            addr.save()

    def handle(self, **options):
        http = HttpFetcher()
        http.set_cache_dir(os.path.join(settings.PROJECT_ROOT, ".cache"))
        self.data_path = os.path.join(settings.PROJECT_ROOT, '..', 'data')
        self.http = http
        print "Importing municipalities"
        self.import_municipalities()
        print "Importing addresses"
        self.import_addresses()
