#! /usr/bin/env perl
# update banshee database to use flac file

use warnings;
use strict;

use DBI;
use File::Glob qw(:glob);
use Getopt::Long;
use Pod::Usage;
use URI::Escape;

my $pkg = 'banshee-2flac';
my $version = '0.3';

my ($check, $ignore_case, $verbose);
my %new = (ext => '.flac', mime => 'taglib/flac');
if (!&GetOptions(help => sub { &pod2usage(-exitval => 0) },
                 check => \$check,
                 'ignore-case' => \$ignore_case,
                 mp3 => sub { %new = (ext => '.mp3', mime => 'taglib/mp3') },
                 verbose => \$verbose,
                 version => sub { print "$pkg $version\n"; exit(0) }))
{
    warn("Try ``$pkg --help'' for more information.\n");
    exit(1);
}

# get artist and album
if (@ARGV < 2) {
    warn("$pkg: improper number of arguments: @ARGV\n");
    warn("Try ``$pkg --help'' for more information.\n");
    exit(1);
}
my ($artist, $album, $track) = @ARGV;

# connect to database
my $bdb = "$ENV{HOME}/.config/banshee-1/banshee.db";
my $dbh = DBI->connect(
    "dbi:SQLite:dbname=$bdb", '', '', { RaiseError => 1, AutoCommit => 0 }
);
if (!defined($dbh)) {
    warn("$pkg: failed to open Banshee database");
    exit(1);
}

# prepare select query (will not work for multi-artist albums)
my $track_q = qq(
  select t.TrackID, t.Uri, t.MimeType
  from CoreTracks as t
    join CoreArtists as a on a.ArtistID = t.ArtistID
    join CoreAlbums as l on l.AlbumID = t.AlbumID
  where a.Name = ?
    and l.Title = ?
    and t.MimeType != ?
);
my @track_args = ($artist, $album, $new{mime});
if ($track) {
    $track_q .= "\n    and TrackNumber = ?";
    push(@track_args, $track);
}
my $track_s = $dbh->prepare($track_q);

# prepare update query
my $update_q = q(
  update CoreTracks
  set Uri = ?, MimeType = ?, FileSize = ?
  where TrackID = ?
);
my $update_s = $dbh->prepare($update_q);

# get tracks and start loop
$track_s->execute(@track_args);
my ($tracks, $updates) = (0, 0);
while (my $row = $track_s->fetchrow_arrayref) {
    ++$tracks;
    my ($id, $uri, $mime) = @$row;

    # convert the uri to a pathname
    my $path = uri_unescape($uri);
    $path =~ s,^file://,,;
    if (! -f $path) {
        warn("$pkg: file missing: $path\n");
        next; # while $row
    }

    # try to find the same flac file
    my $ext = $mime;
    $ext =~ s,^taglib/,,;
    my $flac = $path;
    my $flac_uri = $uri;
    $flac =~ s/\.$ext$/$new{ext}/;
    $flac_uri =~ s/\.$ext$/$new{ext}/;
    if (!-f $flac) {
        if ($ignore_case) {
            # try a case insensitive match (need to have a glob character)
            my $flac_glob = $flac;
            my $last_char = chop($flac_glob);
            $flac_glob = $flac_glob . '[' . $last_char . ']';
            my ($match) = bsd_glob($flac_glob, GLOB_NOCASE);
            if (!$match) {
                warn("$pkg: no flac file matched: $flac\n");
                next; # while $row
            }
            # else
            $flac = $match;
            # do our best on uri
            $flac_uri = "file://$flac";
            $flac_uri =~ s/ /%20/g;
            $flac_uri =~ s/\[/%5B/g;
            $flac_uri =~ s/\]/%5D/g;
            $flac_uri =~ s/\#/%23/g;
        }
        else {
            warn("$pkg: no flac file matched: $flac\n");
            next; # while $row
        }
    }

    # get file size
    my $flac_size = -s $flac;

    # update track
    ++$updates;
    if ($check) {
        print("$pkg: $id: $flac_size\n  $uri\n  $flac_uri\n") if $verbose;
        next;
    }
    # else
    $update_s->execute($flac_uri, $new{mime}, $flac_size, $id);
}
print("$pkg: processed $tracks tracks, updated $updates tracks\n");

$track_s->finish;
$update_s->finish;
$dbh->commit;
$dbh->disconnect;

exit(0);

__END__

=pod

=head1 NAME

banshee-2flac - update banshee database to use flac

=head1 SYNOPSIS

B<banshee-2flac> [OPTIONS]... ARTIST ALBUM [N]

=head1 DESCRIPTION

This script updates the banshee music database to use a FLAC file, if it
exists, rather than a compressed audio file format.  The script will
update an entire album if given the ARTIST name and ALBUM title.  If the
optional track number is also give, it will update just that track (this
is useful if an album was previously updated but some tracks failed due
to file name mismatching).

=head1 OPTIONS

If an argument to a long option is mandatory, it is also mandatory for
the corresponding short option; the same is true for optional arguments.

=over 4

=item -c, --check

Print what would be done, but do not do anything.

=item -h, --help

Display a brief description and listing of all available options.

=item -i, --ignore-case

Ignore case when attempting to match the original and FLAC file names.

=item -m, --mp3

Convert to MP3 rather than FLAC.

=item -v, --version

Output version information and exit.

=item --

Terminate option processing.  This option is useful when file names
begin with a dash (-).

=back

=head1 BUGS

No known bugs.

=head1 SEE ALSO

banshee(1)

=head1 AUTHOR

David Dooling <dooling@gmail.com>

=cut
