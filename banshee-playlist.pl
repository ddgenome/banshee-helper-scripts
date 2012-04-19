#! /usr/bin/env perl
# create m3u file for banshee playlist
use warnings;
use strict;

use DBI;
use File::Basename;
use Getopt::Long;
use IO::File;
use Pod::Usage;
use URI::Escape;

my $pkg = 'banshee-playlist';
my $version = '0.2';

my $db = "$ENV{HOME}/.config/banshee-1/banshee.db";
my ($export, $list, $quiet);
unless (GetOptions(help => sub { &pod2usage(-exitval => 0) },
                   'db=s' => \$db,
                   export => \$export,
                   list => \$list,
                   quiet => \$quiet,
                   version => sub { print "$pkg $version\n"; exit(0) }
                  ))
{
    warn("Try `$pkg --help' for more information.\n");
    exit(1);
}

# connect to database
die("$pkg: banshee database does not exist or is not readable")
    unless (-f $db && -r $db);
my $dbh = DBI->connect("dbi:SQLite:dbname=$db", '', '',
                       { RaiseError => 1, AutoCommit => 0 });

# see what user wants
if ($list) {
    &list_playlists($dbh);
}
else {
    # get playlist
    die("$pkg: incorrect number of arguments: @ARGV") unless @ARGV == 1;
    my ($playlist) = @ARGV;

    &get_list($dbh, $playlist, $export);
}

$dbh->disconnect;

exit(0);

# list the playlists
sub list_playlists {
    my ($dbh) = @_;

    my $list_q = q(select PlaylistID, Name from CorePlaylists);
    my $list_s = $dbh->prepare($list_q);
    $list_s->execute();
    while (my $row = $list_s->fetchrow_arrayref) {
        my ($id, $name) = @$row;
        print("$name\n");
    }
    return;
}

sub get_list {
    my ($dbh, $playlist, $export) = @_;

    # prep query
    my $track_q = q(
      select t.Uri, e.ViewOrder, a.Name, t.Title, t.TrackNumber,
        l.Title, t.Year, t.Genre
      from CoreTracks as t
        join CoreArtists as a on t.ArtistID = a.ArtistID
        join CoreAlbums as l on t.AlbumID = l.AlbumID
        join CorePlaylistEntries as e on t.TrackID = e.TrackID
        join CorePlaylists as p on e.PlaylistID = p.PlaylistID
      where p.Name = ?
      order by e.ViewOrder
    );
    my $track_s = $dbh->prepare($track_q);
    # execute query
    $track_s->execute($playlist);

    # open m3u file
    my $m3u = IO::File->new(">$playlist.m3u");
    die "$pkg: failed to open m3u file: $!" unless defined($m3u);
    $m3u->print("#EXTM3U\n");

    # get tracks and start loop
    while (my $row = $track_s->fetchrow_arrayref) {
        my (%track);
        @track{qw(uri order artist title n album year genre)} = @$row;
        my $path = $track{uri};
        $path =~ s,^file://,,;
        $path = uri_unescape($path);
        if (! -f $path) {
            warn("$pkg: file does not exist: '$path'\n");
        }
        if ($export) {
            my $rv = &export_file($path, %track);
            if (!$rv) {
                warn("$pkg: failed to export file: $path");
            }
            else {
                $path = $rv;
            }
        }
        $m3u->print("#EXTINF:$track{order},$track{artist} - $track{title}\n");
        $m3u->print("$path\n");
    }
    $m3u->close;
}

# export music files
sub export_file {
    my ($path, %track) = @_;

    # parse file path
    my @exts = qw(.mp3 .ogg .flac .m4a);
    my ($base, $dir, $suffix) = fileparse($path, @exts);
    if (!$suffix) {
        warn("$pkg: unknown suffix: $path");
        return;
    }
    my $wav = "$base.wav";
    my $mp3 = "$base.mp3";
    print("$pkg: export $path to $mp3\n") unless $quiet;

    # see if our work is already done
    if (-f $mp3) {
        warn("$pkg: file already exists: $mp3");
        return $mp3;
    }

    # create wav
    my @wav_cmd = (qw(mplayer -really-quiet -nolirc -vo null -vc dummy -ao),
                   "pcm:waveheader:file=$wav", $path);
    if (system(@wav_cmd) != 0) {
        warn("$pkg: failed to convert audio file to wav: $path");
        return;
    }

    # create mp3
    my @lame_cmd = (qw(lame --quiet --preset medium), '--ta', $track{artist},
                    '--tl', $track{album}, '--ty', $track{year},
                    '--tn', $track{n}, '--tg', $track{genre},
                    '--tt', $track{title}, $wav, $mp3);
    if (system(@lame_cmd) != 0) {
        warn("$pkg: failed to convert wav to mp3: $path");
        unlink($wav);
        return;
    }
    unlink($wav);

    return $mp3;
}

__END__

=pod

=head1 NAME

banshee-playlist - list contents of banshee playlists

=head1 SYNOPSIS

B<banshee-playlist> [OPTIONS]... [PLAYLIST]

=head1 DESCRIPTION

This programs reads a Banshee database and outputs playlist
information.  It can create an m3u file for a PLAYLIST (the default),
list the available playlists, and optionally export the song music
files from a playlist.

=head1 OPTIONS

If an argument to a long option is mandatory, it is also mandatory for
the corresponding short option; the same is true for optional arguments.

=over 4

=item --db=PATH

Use PATH for banshee database rather than the default,
C<~/.config/banshee-1/banshee.db>.

=item --export

Write the m3u file and export the music files as LAME-encoded medium
quality MP3 files in the current directory.

=item --help

Display a brief description and listing of all available options.

=item --list

List the banshee playlists.

=item --version

Output version information and exit.

=item --

Terminate option processing.  This option is useful when file names
begin with a dash (-).

=back

=head1 EXAMPLES

To get a list of the playlists in banshee, run

  $ banshee-playlist --list

To write an m3u file for playlist Workout and export the song files to
the current directory, run

  $ banshee-playlist --export Workout

=head1 BUGS

Please email the author if you identify a bug.

=head1 SEE ALSO

sqlite3(1), banshee(1)

=head1 AUTHOR

David Dooling <banjo@users.sourceforge.net>

=cut
