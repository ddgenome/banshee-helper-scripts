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

import os
import pprint
import re
import sqlite3
import sys
# https://github.com/simon-weber/Unofficial-Google-Music-API
from gmusicapi.api import Api
from getpass import getpass

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
    """Create dictionary key from track information."""

    # compile regular expression
    re_paren = re.compile('[[(][^)\]]*[)\]]')
    re_nonword = re.compile('[^\w\s]')
    re_mspace = re.compile('[\s]')
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
        # remove junk
        #item = re_nonword.sub('', item)
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
    print "Loading library...",
    gm_library = api.get_all_songs()
    print "done."

    print len(gm_library), "gm tracks found."

    for song in gm_library:
        if song['titleNorm'] == u'surrender':
            #pp = pprint.PrettyPrinter(indent=4)
            #pp.pprint(song)
            break

    # collect gm tracks
    gm_tracks = {}
    gm_dups = {}
    for t in gm_library:
        # check input data
        if not 'track' in t:
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
            print 'unknown file type: ', (t['uri'])
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

def main():
    """Main subroutine."""

    # make a new instance of the api and prompt the user to log in
    api = init()

    if not api.is_authenticated():
        print "Sorry, those credentials weren't accepted."
        return

    print "Successfully logged in."

    # get the google music library
    (gm_tracks, gm_dups) = get_gm_library(api)

    # get the banshee library
    (b_tracks, b_dups) = get_b_library(3)

    # loop through b_tracks to see if they exist in gm
    no_gm = {}
    for t_key in b_tracks:
        if not t_key in gm_tracks:
            #print 'no gm:', t_key
            no_gm[t_key] = b_tracks[t_key]

    print "gm tracks", len(gm_tracks)
    print "gm dups", len(gm_dups)
    print "banshee tracks", len(b_tracks)
    print "banshee dups", len(b_dups)
    print "gm missing tracks", len(no_gm)

    # FIXME

    # logout of gm
    api.logout()

if __name__ == '__main__':
    main()
    sys.exit(0)
