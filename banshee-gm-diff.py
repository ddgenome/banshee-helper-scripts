#!/usr/bin/env python

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
import sqlite3
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

def main():
    """Demonstrates some api features."""

    #Make a new instance of the api and prompt the user to log in.
    api = init()

    if not api.is_authenticated():
        print "Sorry, those credentials weren't accepted."
        return

    print "Successfully logged in."
    print

    #Get all of the users songs.
    #library is a big list of dictionaries, each of which contains a single song.
    print "Loading library...",
    library = api.get_all_songs()
    print "done."

    print len(library), "gm tracks detected."
    #print

    # collect gm tracks
    gm_tracks = {}
    for t in library:
        key_items = [t['track'], t['title'], t['album'], t['artist']]
        key_items_u = map(unicode, key_items)
        key_items_lc = map(unicode.lower, key_items_u)
        key = '|'.join(key_items_lc)
        if key in gm_tracks:
            print "Google track appears multiple times: {0}, {1}".format(
                    gm_tracks[key], t['id'])
        else:
            gm_tracks[key] = t['id']

    #Show some info about a song. There is no guaranteed order;
    # this is essentially a random song.
    #first_song = library[0]
    #pp = pprint.PrettyPrinter(indent=4)
    #pp.pprint(first_song)
    #print "The first song I see is '{0}' by '{1}'.".format(
    #    first_song["title"],
    #    first_song["artist"])

    # connect to banshee database
    banshee_conn = sqlite3.connect(os.environ['HOME']
        + '/.config/banshee-1/banshee.db')
    banshee_c = banshee_conn.cursor()
    # get all songs with a three or better rating
    banshee_c.execute('''
      select t.TrackID, t.Uri, t.Title, t.TrackNumber, t.Duration, t.Disc,
        a.Name, l.Title
      from CoreTracks as t
        join CoreArtists as a on t.ArtistID = a.ArtistID
        join CoreAlbums as l on t.AlbumID = l.AlbumID
      where t.Rating > 2''')
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
        key_items = [t['n'], t['title'], t['album'], t['artist']]
        key_items_u = map(unicode, key_items)
        key_items_lc = map(unicode.lower, key_items_u)
        key = '|'.join(key_items_lc)
        if key in b_tracks:
            print "Banshee track appears multiple times: {0}, {1}".format(
                    b_tracks[key], t['uri'])
        else:
            b_tracks[key] = t['uri']

    print len(b_tracks), "banshee tracks found."

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


    #It's good practice to logout when finished.
    #api.logout()
    print "All done!"

if __name__ == '__main__':
    main()
