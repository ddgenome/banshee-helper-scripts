#! /usr/bin/env python
# perform various push operations from banshee to Google Play Music

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
from optparse import OptionParser
from distutils.dir_util import mkpath
# https://github.com/simon-weber/Unofficial-Google-Music-API
from gmusicapi.api import Api
from getpass import getpass

# setup stdout and stderr for utf-8
reload(sys)
sys.setdefaultencoding('utf-8')
sys.stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stderr = codecs.getwriter('utf8')(sys.stderr)

pkg = 'banshee-gm'
version = '0.3'

# change to True to not create files or change gm library information
# will still get all information, do comparisons, and print out what would
# have been done
dryrun = False

def logmsg(msg, error=False):
    """Print status messages and write to log file.

    :param msg: text of message to record
    :param error: set to True if it is an error message
    """

    text = u"{0}: {1}".format(pkg, msg)
    if error:
        sys.stderr.write(text + u'\n')
    else:
        print text 
    logmsg.log_f.write(u"{0}\n".format(msg))
    return

def write_keys(filename, d):
    '''Write sorted keys from dictionary in filename.

    :param filename: name of file to write to
    :param d: dictionary with keys to be written
    '''

    # make sure there is something to write
    if d:
        with codecs.open(filename, mode='w', encoding='utf-8') as f:
            for k in sorted(d.keys()):
                f.write(k + '\n')

    return

def make_track_key(n, title, album, artist):
    """Create dictionary key from track information.

    :param: n: track number
    :param title: track title
    :param album: track album
    :param artist: track artist

    This method creates a string from the arguments after some cleaning,
    allowing for fuzzy matching of tracks while doing its level best to
    prevent false duplicates.
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

def gm_track_to_key(gm_track):
    '''Convert a Google Music track dictionary to a dictionary key.

    :param gm_track: Google Music API track dictionary

    This method ensures that the track number is set.  This method uses
    make_track_key under the hood.
    '''

    # make sure dictionary has a track number entry
    if 'track' not in gm_track:
        gm_track['track'] = 0

    # get track key
    return make_track_key(gm_track['track'], gm_track['title'],
                          gm_track['album'], gm_track['artist'])

def get_gm_library(api):
    """Download tracks metadata and return in dictionary.

    :param api: Google Music API connection
    """

    # get all of the users songs
    # library is a list of dictionaries, each of which contains a single song
    logmsg("loading google music library")
    gm_library = api.get_all_songs()
    logmsg("google music library loading complete")

    # collect gm tracks
    gm_tracks = {}
    gm_dups = {}
    gm_zeros = {}
    for t in gm_library:
        # generate track key
        key = gm_track_to_key(t)

        # record tracks with zero track number
        if t['track'] == 0:
            gm_zeros[key] = t

        # check for duplicates
        if key in gm_tracks:
            if key in gm_dups:
                gm_dups[key].append(t)
            else:
                gm_dups[key] = [gm_tracks[key], t]
        else:
            gm_tracks[key] = t

    # report metrics
    logmsg("google music tracks: {0}".format(len(gm_library)))
    logmsg("google music tracks without number: {0}".format(len(gm_zeros)))
    logmsg("google music dups: {0}".format(len(gm_dups)))
    logmsg("google music unique tracks: {0}".format(len(gm_tracks)))

    # write problematic tracks
    write_keys('gm.zero', gm_zeros)
    write_keys('gm.dup', gm_dups)

    return gm_tracks

def get_gm_playlists(api):
    '''Return dictionary of Google Music playlists.

    :param api: Google Music API connection

    The dictionary has the name of the playlists as its keys and the values
    for each element is a list of the track keys.
    '''

    # get user playlists
    playlist_ids = api.get_all_playlist_ids(auto=False, instant=False,
                                            user=True, always_id_lists=True)
    # loop through names
    gm_playlists = {}
    for (name, ids) in playlist_ids['user'].iteritems():
        # reject duplicates
        if len(ids) > 1:
            logmsg('multiple google music playlists with same name: {0}'.format(
                    name), True)
            continue

        # get tracks
        p_tracks = api.get_playlist_songs(ids[0])

        # initialize list
        gm_playlists[name] = []

        # loop through songs
        for t in p_tracks:
            # get track key
            key = gm_track_to_key(t)
            gm_playlists[name].append(key)

    return gm_playlists

def get_b_library(banshee_conn, rating):
    """Read Banshee database and return dictionary tracks with rating greater than RATING.

    :param banshee_conn: connection to Banshee database
    :param rating: minimum rating of tracks to return

    Dictionary keys are the standard track keys and the values are the URI
    for the track.  Only local files (file:// URIs) are considered.
    """

    banshee_c = banshee_conn.cursor()
    # get all songs with a three or better rating
    t = (rating,)
    banshee_c.execute('''
      select t.TrackID, t.Uri, t.Title, t.TrackNumber, t.Duration, t.Disc,
        t.Rating, t.PlayCount, a.Name, l.Title
      from CoreTracks as t
        join CoreArtists as a on t.ArtistID = a.ArtistID
        join CoreAlbums as l on t.AlbumID = l.AlbumID
      where t.Rating >= ?''', t)

    # compile regular expressions
    re_prefix = re.compile('^file://' + os.environ['HOME'] + '/Music')
    re_pdf = re.compile('\.pdf$', re.I)
    re_mime = re.compile('\.(ogg|flac|mp3|m4a|wma)$', re.I)

    # process tracks
    b_tracks = {}
    b_dups = {}
    rows = 0
    tracks = 0
    for row in banshee_c:
        # increment row counter
        ++rows

        # would be nice if you could do slice assignment with dictionary
        t = {}
        (t['id'], t['uri'], t['title'], t['n'], t['time'], t['disc'],
         t['rating'], t['playcount'], t['artist'], t['album']) = row

        # only look at local files
        if not re_prefix.search(t['uri']):
            continue

        # skip pdf files
        if re_pdf.search(t['uri']):
            continue

        # check for know file types
        if not re_mime.search(t['uri']):
            logmsg('unknown file type: {0}'.format(t['uri']))
            continue

        # looks like a real music track
        ++tracks

        # create dictionary key
        key = make_track_key(t['n'], t['title'], t['album'], t['artist'])

        # see if track is a duplicate
        if key in b_tracks:
            if key in b_dups:
                b_dups[key].append(t['uri'])
            else:
                b_dups[key] = [b_tracks[key]['uri'], t['uri']]
        else:
            b_tracks[key] = t

    # report metrics
    logmsg('banshee rows: {0}'.format(rows))
    logmsg('banshee tracks: {0}'.format(tracks))
    logmsg("banshee dups: {0}".format(len(b_dups)))
    logmsg("banshee unique tracks: {0}".format(len(b_tracks)))

    # write banshee dups
    write_keys('b.dup', b_dups)

    return b_tracks

def get_b_playlists(banshee_conn, playlists=[]):
    '''Return dictionary of Banshee playlists.

    :param banshee_conn: connection to Banshee database
    :param playlists: playlists to return (return all if none specified)

    The dictionary has the names of the playlists as its keys and a list
    of track keys as its values.
    '''

    pl_to_get = []
    # see if playlists were provided
    if playlists:
        # make sure they exist
        for p_name in playlists:
            banshee_c = banshee_conn.cursor()
            t = (p_name,)
            banshee_c.execute('select count(*) from CorePlayLists where Name = ?', t)
            count = banshee_c.fetchone()[0]
            if count == 0:
                logmsg('banshee playlist does not exist: {0}'.format(p_name),
                       True)
                # need to check smart playlists
            elif count > 1:
                logmsg('multiple banshee playlists match: {0}'.format(p_name),
                       True)
            elif count == 1:
                pl_to_get.append(p_name)
            else:
                logmsg('invalid count for playlist {0}: {1}'.format(p_name, count))
                continue
    else:
        # get all playlists from banshee database
        banshee_c = banshee_conn.cursor()
        banshee_c.execute('select Name from CorePlaylists')
        # put them in a list
        pl_to_get = [row[0] for row in banshee_c.fetchall()]

    # loop through playlists
    b_playlists = {}
    for p_name in pl_to_get:
        # get cursor for playlist query
        banshee_p_c = banshee_conn.cursor()
        t = (p_name,)
        banshee_p_c.execute('''
          select e.ViewOrder, a.Name, t.Title, t.TrackNumber, l.Title
          from CoreTracks as t
            join CoreArtists as a on t.ArtistID = a.ArtistID
            join CoreAlbums as l on t.AlbumID = l.AlbumID
            join CorePlaylistEntries as e on t.TrackID = e.TrackID
            join CorePlaylists as p on e.PlaylistID = p.PlaylistID
          where p.Name = ?
          order by e.ViewOrder, e.EntryID''', t)

        # loop through playlist tracks
        b_playlists[p_name] = []
        for trow in banshee_p_c:
            (pn, artist, title, n, album) = trow
            # create key
            key = make_track_key(n, title, album, artist)
            b_playlists[p_name].append(key)

    return b_playlists

def link_tracks(tracks, up=False):
    """Create directory structure and hard link tracks in Banshee that need to be in Google Music.

    :param tracks: dictionary of track key,uri values
    :param up: create links in ~/GoogleMusicUp rather than ~/GoogleMusic

    This method with create links for files in the tracks dictionary and
    remove links for files not in it.  Return True if successful.
    """

    # set root paths
    home = os.environ['HOME']
    src_root = home + '/Music'
    target_root =  home + '/GoogleMusic'
    if up:
        target_root = target_root + 'Up'

    # prepare regex
    local_uri_re = re.compile('^file://')
    src_root_re = re.compile('^' + src_root)

    # dictionary for valid links
    valid_links = {}
    # iterate over items that need to be created
    for (key, uri) in tracks.iteritems():
        # make sure it is local
        if not local_uri_re.match(uri):
            logmsg('not a local file: {0}'.format(uri), True)
            continue

        # unescape uri (avoid unicode confusion by forcing ascii)
        src_uri = urllib.unquote(uri.encode('ascii'))
        # remove protocol (file://)
        src = src_uri[7:]
        # initiate link path
        link = src_root_re.sub(target_root, src)
        # determine real paths (avoid sym link issues)
        src_real = os.path.realpath(src)
        link_real = os.path.realpath(link)
        # store valid links for later pruning
        valid_links[link_real] = 1

        # see if link already exists
        if os.path.exists(link_real):
            continue

        # make sure source exists
        if not os.path.exists(src_real):
            logmsg(u'original file does not exist: {0}, {1}, {2}'.format(uri,
                   src_uri, src), True)
            continue

        # create path to link
        link_dir = os.path.dirname(link_real)
        if not dryrun and not os.path.exists(link_dir):
            if not mkpath(link_dir):
                logmsg(u'failed to create dir: {0}'.format(link_dir), True)
                continue
        # create hard link
        try:
            if not dryrun:
                os.link(src_real, link_real)
        except OSError:
            logmsg(u'failed to link: {0}, {1}'.format(src_real, link_real),
                   True)
            continue

        logmsg(u"created link: {0}".format(link_real))

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
            if not dryrun:
                os.unlink(path)
            logmsg("removed: {0}".format(path))

    # loop again to find empty directories
    for (root, dirs, files) in os.walk(target_root_real, topdown=False):
        for d in dirs:
            path = os.path.join(root, d)
            if not os.listdir(path):
                if not dryrun:
                    os.rmdir(path)
                logmsg(u"removed empty directory: {0}".format(path))

    return True

# above are the helper methods
# below are the task-oriented methods

def diff(gm_tracks, b_tracks):
    """Create directory structure for Banshee tracks not in Google Music.

    :param gm_tracks: dictionary of Google Music entries
    :param b_tracks: dictionary of Banshee tracks
    """

    # loop through b_tracks to see if they exist in gm
    no_gm = {}
    for t_key in b_tracks:
        if t_key not in gm_tracks:
            #print 'no gm:', t_key
            no_gm[t_key] = b_tracks[t_key]['uri']

    logmsg("gm missing tracks {0}".format(len(no_gm)))

    # write tracks that need to up uploaded
    write_keys('b-gm.up', no_gm)

    # create directory suitable for google music manager
    return link_tracks(no_gm, True)

def sync(b_tracks):
    """Create directory structure of Banshee tracks.

    :param b_tracks: dictionary of Banshee tracks
    """

    # simplify b_tracks to just have uri values
    b_uri = {}
    for (key, t) in b_tracks.iteritems():
        b_uri[key] = t['uri']

    # write tracks that need to up uploaded
    write_keys('b-gm.sync', b_uri)

    # create directory suitable for google music manager
    return link_tracks(b_uri)

def track(api, gm_tracks, b_tracks):
    '''Update Google Music track metadata using information from Banshee database.

    :param api: Google Music API connection
    :param gm_tracks: Google Music track dictionary
    :param b_tracks: Banshee track dictionary

    This only updates the rating and playcount.  Return True if successful.
    '''

    # loop through banshee tracks
    updates = []
    for (key, b_track) in b_tracks.iteritems():
        # see if tracks is in google music
        if key not in gm_tracks:
            logmsg('banshee track not in google music: {0}'.format(key), True)
            continue

        # create updated track dictionary
        update = {}
        for (gm_k, gm_v) in gm_tracks[key].iteritems():
            if gm_k == 'rating':
                # banshee rating overrides any rating in gm
                update[gm_k] = b_track['rating']
            elif gm_k == 'playCount':
                # add play counts together
                update[gm_k] = b_track['playcount'] + gm_v
            else:
                update[gm_k] = gm_v

        updates.append(update)

    # update google music track metadata
    logmsg('updating information for tracks: {0}'.format(len(updates)))
    if not dryrun:
        updated = api.change_song_metadata(updates)
        if updated:
            logmsg('updated metadata for tracks: {0}'.format(len(updated)))
        else:
            logmsg('failed to update metadata for tracks', True)

    return True

def playlist(api, gm_tracks, b_playlists):
    '''Create Banshee playlists in Google Music.

    :param api: Google Music API connection
    :param gm_tracks: dictionary of Google Music tracks
    :param b_playlists: dictionary of Banshee playlists to upload
    '''

    # get google music playlists
    gm_playlists = get_gm_playlists(api)

    # loop through banshee playlists
    for (playlist_name, tracks) in b_playlists.iteritems():
        if playlist_name in gm_playlists:
            logmsg('banshee playlist already exists as google music playlist: {0}'.format(playlist_name), True)
            continue

        # create playlist
        if not dryrun:
            playlist_id = api.create_playlist(playlist_name)
        logmsg('created google music playlist: {0}'.format(playlist_name))

        # loop through songs
        p_tracks = []
        for t_key in tracks:
            # make sure song exists in gm_tracks
            if t_key not in gm_tracks:
                logmsg('playlist track not in google music library: {0}, {1}'.format(playlist_name, t_key), True)
                continue

            # get gm track id
            track_id = gm_tracks[t_key]['id']
            if not track_id:
                logmsg('google music track has no id: {0}, {1}'.format(
                       playlist_name, t_key), True)
                continue

            p_tracks.append(track_id)
            logmsg('added track to {0}: {1}'.format(playlist_name, t_key))

        # add tracks to playlist (hopefully order is preserved)
        if not dryrun:
            api.add_songs_to_playlist(playlist_id, p_tracks)

    return True

def main(argv):
    '''Farm out work to task-based methods.

    :param argv: list of command line arguments
    '''

    # open log file
    logmsg.log_f = codecs.open(pkg + '.log', mode='w', encoding='utf-8')

    # process command line options
    usage = "%prog [OPTIONS]... [COMMAND] [ARGS]..."
    version_str = "{0} {1}".format(pkg, version)
    parser = OptionParser(usage=usage, version=version_str)
    # default banshee database
    banshee_db_def = os.environ['HOME'] + '/.config/banshee-1/banshee.db'
    banshee_db_help = "use Banshee database BANSHEE_DB (default {0})".format(banshee_db_def)
    parser.add_option("-b", "--banshee-db", default=banshee_db_def,
                      help=banshee_db_help)
    parser.add_option("-d", "--dry-run", action="store_true", default=False,
                      help="perform no action, just report what would be done")
    parser.add_option("-q", "--quiet", action="store_true",
                      help="do not print status messages")
    # default minimum rating
    rating_def = 3
    rating_help = "only consider Banshee songs with rating >= RATING (default {0})".format(rating_def)
    parser.add_option("-r", "--rating", type="int", default=rating_def,
                      help=rating_help)

    (options, args) = parser.parse_args()
    # set "global"
    dryrun = options.dry_run

    # determine action
    command = 'diff'
    if len(args):
        command = args[0]
        args = argv[1:]

    # log in to Google Music (gm)
    api = Api() 

    gm_tracks = {}
    # sync does not need connection to gm
    if command != 'sync':
        logged_in = False
        attempts = 0
        while not logged_in and attempts < 3:
            email = raw_input("Email: ")
            password = getpass()

            logged_in = api.login(email, password)
            attempts += 1

        if not api.is_authenticated():
            logmsg('google credentials were not accepted', True)
            return

        logmsg("successfully logged in to google")

        # get the google music library
        gm_tracks = get_gm_library(api)

    # connect to banshee database
    banshee_conn = sqlite3.connect(options.banshee_db)
    if not banshee_conn:
        logmsg('unable to connect to banshee: {0}'.format(options.banshee_db),
               True)
        return

    # get the banshee library
    b_tracks = get_b_library(banshee_conn, options.rating)

    # dispatch
    rv = 0
    if command == 'diff':
        # create files not in google music
        rv = diff(gm_tracks, b_tracks)
    elif command == 'sync':
        # create all files with sufficient rating
        rv = sync(b_tracks)
    elif command == 'track':
        # update track metadata
        rv = track(api, gm_tracks, b_tracks)
    elif command == 'playlist':
        # get banshee playlists
        b_playlists = get_b_playlists(banshee_conn, args)
        # upload banshee playlists to google music
        rv = playlist(api, gm_tracks, b_playlists)
    else:
        logmsg('unknown command: {0}'.format(command), True)
        return

    # logout of gm
    api.logout()

    # disconnect from banshee database
    banshee_conn.close()

    # close log file
    logmsg.log_f.close

    if rv:
        sys.exit(0)
    # else
    sys.exit(1)
    # just in case
    return

if __name__ == '__main__':
    rv = main(sys.argv)
