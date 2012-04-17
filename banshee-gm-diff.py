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

    # create dictionary key
    key_items = [n, title, album, artist]
    key_items_u = map(unicode, key_items)
    key_items_lc = map(unicode.lower, key_items_u)
    key = '|'.join(key_items_lc)

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
    for t in gm_library:
        # check input data
        if not 'track' in t:
            t['track'] = 0
        key = make_track_key(t['track'], t['title'], t['album'], t['artist'])
        if t['track'] == 0:
            print "gm no track number:", key

        # check for dups
        if key in gm_tracks:
            print 'gm dup: ', key
            #pp = pprint.PrettyPrinter(indent=4)
            #pp.pprint(gm_tracks[key])
            #pp.pprint(t)
        else:
            gm_tracks[key] = t

    return gm_tracks

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
    # record tracks
    b_tracks = {}
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
        prefix = re.compile('^file://' + os.environ['HOME'] + '/Music')
        if not prefix.search(t['uri']):
            continue

        # skip pdf files
        pdf = re.compile('\.pdf$', re.I)
        if pdf.search(t['uri']):
            continue

        # check for know file types
        mime = re.compile('\.(ogg|flac|mp3|m4a)$', re.I)
        if not mime.search(t['uri']):
            print 'unknown file type: ', (t['uri'])
            continue

        # create dictionary key
        key = make_track_key(t['n'], t['title'], t['album'], t['artist'])

        # see if track is a duplicate
        if key in b_tracks:
            print "Banshee track appears multiple times: {0}, {1}".format(
                    b_tracks[key], t['uri'])
        else:
            b_tracks[key] = t['uri']

    print len(b_tracks), "banshee tracks found."

    return b_tracks

def main():
    """Main subroutine."""

    # get the google music library
    # make a new instance of the api and prompt the user to log in
    api = init()

    if not api.is_authenticated():
        print "Sorry, those credentials weren't accepted."
        return

    print "Successfully logged in."

    gm_tracks = get_gm_library(api)

    # get the banshee library
    b_tracks = get_b_library(3)

    # loop through btracks to see if they exist in gm
    no_gm = {}
    for t_key in b_tracks:
        if not t_key in gm_tracks:
            #print 'no gm:', t_key
            no_gm[t_key] = b_tracks[t_key]
            
    print "gm missing tracks", len(no_gm)

    #We're going to create a new playlist and add a song to it.
    #Songs are uniquely identified by 'song ids', so let's get the id:
    #song_id = first_song["id"]

    #print "I'm going to make a new playlist and add that song to it."
    #print "Don't worry, I'll delete it when we're finished."
    #print
    #playlist_name = raw_input("Enter a name for the playlist: ")

    #Like songs, playlists have unique ids.
    #Note that Google Music allows more than one playlist of the
    # exact same name, so you'll always have to work with ids.
    #playlist_id = api.create_playlist(playlist_name)
    #print "Made the playlist."
    #print

    #Now lets add the song to the playlist, using their ids:
    #api.add_songs_to_playlist(playlist_id, song_id)
    #print "Added the song to the playlist."
    #print

    #We're all done! The user can now go and see that the playlist is there.
    #raw_input("You can now check on Google Music that the playlist exists. \n When done, press enter to delete the playlist:")
    #api.delete_playlist(playlist_id)
    #print "Deleted the playlist."


    # logout of gm
    api.logout()

if __name__ == '__main__':
    main()
    sys.exit(0)
