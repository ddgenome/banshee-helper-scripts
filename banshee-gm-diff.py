#! /usr/bin/env python
# diff banshee and google music libraries

# Copyright (c) 2012, Simon Weber
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the
#       names of the contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import codecs
import os
import re
import sqlite3
import sys
import urllib
from distutils.dir_util import mkpath
# https://github.com/simon-weber/Unofficial-Google-Music-API
from gmusicapi.api import Api
from getpass import getpass

# setup stdout and stderr for utf-8
reload(sys)
sys.setdefaultencoding('utf-8')
sys.stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stderr = codecs.getwriter('utf8')(sys.stderr)

pkg = 'banshee-gm-diff'
version = '0.1'

status_f = codecs.open(pkg + '.out', mode='w', encoding='utf-8')
def status(msg):
    """Print status messages."""

    print u"{0}: {1}".format(pkg, msg)
    status_f.write(u"{0}\n".format(msg))
    return

def init():
    """Makes an instance of the api and attempts to login with it.
    Returns the authenticated api.
    """
    
    api = Api() 
    
    logged_in = False
    attempts = 0

    while not logged_in and attempts < 3:
        email = raw_input("Email: ")
        password = getpass()

        logged_in = api.login(email, password)
        attempts += 1

    return api

def make_track_key(n, title, album, artist):
    """Create dictionary key from track information.

    n        track number
    title    track title
    album    track album
    artist   track artist

    This method creates a string from the arguments after some cleaning.
"""

    # compile regular expression
    re_paren = re.compile('[[(][^)\]]*[)\]]')
    re_nonword = re.compile('[^\w\s]')
    re_mspace = re.compile('\s+')
    re_prespace = re.compile('^\s+')
    re_postspace = re.compile('\s+$')

    # create dictionary key
    key_items = []
    for item in [n, title, album, artist]:
        # cast to unicode
        item = unicode(item)
        # lower case
        item = item.lower()
        # remove parenthetical comments
        item = re_paren.sub('', item)
        # remove nonword junk
        item = re_nonword.sub('', item)
        # deal with leading, trailing, and multiple spaces
        item = re_mspace.sub(' ', item)
        item = re_prespace.sub('', item)
        item = re_postspace.sub('', item)

        # add to list
        key_items.append(item)

    key = '|'.join(key_items)

    return key

def get_gm_library(api):
    """Download tracks metadata and return in dictionary"""

    # get all of the users songs
    # library is a list of dictionaries, each of which contains a single song
    status("loading library")
    gm_library = api.get_all_songs()
    status("library loading complete")

    status("{0} gm tracks found".format(len(gm_library)))

    # collect gm tracks
    gm_tracks = {}
    gm_dups = {}
    for t in gm_library:
        # check input data
        if 'track' not in t:
            t['track'] = 0
        key = make_track_key(t['track'], t['title'], t['album'], t['artist'])
        #if t['track'] == 0:
        #    print "gm no track number:", key

        # check for dups
        if key in gm_tracks:
            if key in gm_dups:
                gm_dups[key].append(t)
            else:
                gm_dups[key] = [gm_tracks[key], t]
        else:
            gm_tracks[key] = t

    return (gm_tracks, gm_dups)

def get_b_library(rating):
    """Read Banshee database and return dictionary tracks with rating greater than the argument."""

    # connect to banshee database
    banshee_conn = sqlite3.connect(os.environ['HOME']
        + '/.config/banshee-1/banshee.db')
    banshee_c = banshee_conn.cursor()
    # get all songs with a three or better rating
    t = (rating,)
    banshee_c.execute('''
      select t.TrackID, t.Uri, t.Title, t.TrackNumber, t.Duration, t.Disc,
        a.Name, l.Title
      from CoreTracks as t
        join CoreArtists as a on t.ArtistID = a.ArtistID
        join CoreAlbums as l on t.AlbumID = l.AlbumID
      where t.Rating >= ?''', t)

    # compile regular expressions
    re_prefix = re.compile('^file://' + os.environ['HOME'] + '/Music')
    re_pdf = re.compile('\.pdf$', re.I)
    re_mime = re.compile('\.(ogg|flac|mp3|m4a)$', re.I)

    # process tracks
    b_tracks = {}
    b_dups = {}
    for row in banshee_c:
        t= {}
        t['id'] = row[0]
        t['uri'] = row[1]
        t['title'] = row[2]
        t['n'] = row[3]
        t['time'] = row[4]
        t['disc'] = row[5]
        t['artist'] = row[6]
        t['album'] = row[7]

        # only look at local files
        if not re_prefix.search(t['uri']):
            continue

        # skip pdf files
        if re_pdf.search(t['uri']):
            continue

        # check for know file types
        if not re_mime.search(t['uri']):
            status('unknown file type: {0}'.format(t['uri']))
            continue

        # create dictionary key
        key = make_track_key(t['n'], t['title'], t['album'], t['artist'])

        # see if track is a duplicate
        if key in b_tracks:
            if key in b_dups:
                b_dups[key].append(t['uri'])
            else:
                b_dups[key] = [b_tracks[key], t['uri']]
        else:
            b_tracks[key] = t['uri']

    return (b_tracks, b_dups)

def link_uploads(upload):
    """Create directory structure and hard link tracks in Banshee that need to be uploaded to Google Music."""

    # set root paths and account for sym links
    home = os.environ['HOME']
    src_root = home + '/Music'
    target_root =  home + '/GoogleMusicUp'

    # prepare regex
    local_uri_re = re.compile('^file://')
    src_root_re = re.compile('^' + src_root)

    # dictionary for valid links
    valid_links = {}
    # iterate over items that need to be created
    for (key, uri) in upload.iteritems():
        # make sure it is local
        if not local_uri_re.match(uri):
            sys.stderr.write('not a local file: {0}\n'.format(uri))
            continue

        # unescape uri (avoid unicode confusion by forcing ascii)
        src_uri = urllib.unquote(uri.encode('ascii'))
        # remove protocol (file://)
        src = src_uri[7:]
        # initiate link path
        link = src_root_re.sub(target_root, src)
        # determine real paths
        src_real = os.path.realpath(src)
        link_real = os.path.realpath(link)
        # store valid links for later pruning
        valid_links[link_real] = 1

        # see if link already exists
        if os.path.exists(link_real):
            continue

        # make sure source exists
        if not os.path.exists(src_real):
            sys.stderr.write(u'original file does not exist: {0}, {1}, {2}\n'.format(uri, src_uri, src))
            continue

        # create path to link
        link_dir = os.path.dirname(link_real)
        if not os.path.exists(link_dir):
            if not mkpath(link_dir):
                sys.stderr.write(u'failed to create dir: {0}\n'.format(link_dir))
                continue
        # create hard link
        try:
            os.link(src_real, link_real)
        except OSError:
            sys.stderr.write(u'failed to link: {0}, {1}\n'.format(src_real, link_real))
            continue

        status(u"created link: {0}".format(link_real))

    # remove unneeded files and directories
    target_root_real = os.path.realpath(target_root)
    # loop through all files
    for (root, dirs, files) in os.walk(target_root_real):
        # create full path
        for f in files:
            path = os.path.join(root, f)
            # make sure it does not belong
            if path in valid_links:
                continue
            # rm the file
            os.unlink(path)
            status("removed: {0}".format(path))

    # loop again to find empty directories
    for (root, dirs, files) in os.walk(target_root_real, topdown=False):
        for d in dirs:
            path = os.path.join(root, d)
            if not os.listdir(path):
                os.rmdir(path)
                status(u"removed empty directory: {0}".format(path))

def main():
    """Main subroutine."""

    # make a new instance of the api and prompt the user to log in
    api = init()

    if not api.is_authenticated():
        print "Sorry, those credentials weren't accepted."
        return

    status("successfully logged in")

    # get the google music library
    (gm_tracks, gm_dups) = get_gm_library(api)

    # logout of gm
    api.logout()

    # get the banshee library
    (b_tracks, b_dups) = get_b_library(3)

    # loop through b_tracks to see if they exist in gm
    no_gm = {}
    for t_key in b_tracks:
        if t_key not in gm_tracks:
            #print 'no gm:', t_key
            no_gm[t_key] = b_tracks[t_key]

    status("gm tracks {0}".format(len(gm_tracks)))
    status("gm dups {0}".format(len(gm_dups)))
    status("banshee tracks {0}".format(len(b_tracks)))
    status("banshee dups {0}".format(len(b_dups)))
    status("gm missing tracks {0}".format(len(no_gm)))

    # write gm dups
    with codecs.open('gm.dup', mode='w', encoding='utf-8') as gm_dup_f:
        for k in sorted(gm_dups.keys()):
            gm_dup_f.write(k + '\n')

    # write banshee dups
    with codecs.open('b.dup', mode='w', encoding='utf-8') as b_dup_f:
        for k in sorted(b_dups.keys()):
            b_dup_f.write(k + '\n')

    # write tracks that need to up uploaded
    with codecs.open('b-gm.up', mode='w', encoding='utf-8') as up_f:
        for k in sorted(no_gm.keys()):
            up_f.write(k + '\n')

    # create directory suitable for google music manager
    link_uploads(no_gm)

if __name__ == '__main__':
    main()
    status_f.close
    sys.exit(0)
