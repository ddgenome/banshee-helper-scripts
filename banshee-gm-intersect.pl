#! /usr/bin/env perl
# intersect banshee db and google music html
use warnings;
use strict;

use DBI;
use File::Basename;
use File::Find;
use File::Path qw(make_path);
use Getopt::Long;
use HTML::TreeBuilder;
use IO::Dir;
use IO::Handle;
use Pod::Usage;
use String::Approx qw(amatch);
use URI::Escape;

my $pkg = 'banshee-gm-intersect';
my $version = '0.1';
my $archive = '/home/archive/ddooling';

# do not buffer stdout
STDOUT->autoflush(1);

# process command line options
my ($dryrun, $quiet);
unless (GetOptions(help => sub { &pod2usage(-exitval => 0) },
                   'dry-run' => \$dryrun,
                   quiet => \$quiet,
                   version => sub { print "$pkg $version\n"; exit 0 }))
{
    warn("Try `$pkg --help' for more information.\n");
    exit(1);
}

# parse google music html
die("$pkg: you must supply html file on command line") unless @ARGV > 0;
my ($gm_html) = @ARGV;
die("$pkg: html file does not exist: $gm_html") unless -f $gm_html;
die("$pkg: html is not readable: $gm_html") unless -r $gm_html;
my $tree = HTML::TreeBuilder->new;
print("$pkg: parsing html...") unless $quiet;
$tree->parse_file($gm_html);
print(" done.\n") unless $quiet;
# find song table
my @song_tables = $tree->look_down('id', '0songContainer');
if (@song_tables > 1) {
    warn("$pkg: found more than one song table");
    exit(1);
}
my $song_table = pop(@song_tables);
# loop through table rows collecting tracks
my @gm_tracks;
foreach my $row ($song_table->look_down('_tag', 'tr')) {
    # extract song title, time, artist, album, plays, rating
    my @columns = $row->look_down('_tag', 'td');
    my %track;
    @track{qw(title time artist album plays rating)}
        = map { $_->as_trimmed_text } @columns;
    push(@gm_tracks, { %track });
}
&status("parsed " . @gm_tracks . " gm tracks");
$tree->delete;

# look for duplicates in google music tracks
my %gm_songs;
foreach my $track (@gm_tracks) {
    # create hash key
    my $track_key = join('|', map { lc($track->{$_}) } qw(title artist album));
    &status($track_key);
    # no track number from gm, so unmarked reprise tracks will trigger dup
    if (exists($gm_songs{$track_key})) {
        warn("$pkg: duplicate gm track: $track_key\n");
    }
    ++$gm_songs{$track_key};
}

# connect to banshee database
my $banshee_db = "$ENV{HOME}/.config/banshee-1/banshee.db";
my $dbh = DBI->connect(
    "dbi:SQLite:dbname=$banshee_db",
    '', '', { RaiseError => 1, AutoCommit => 0 }
);
if (!defined($dbh)) {
    warn("$pkg: failed to connect to banshee db: $banshee_db");
    exit(2);
}

# get tracks from library
my $track_q = q(
  select t.TrackID, t.Uri, t.Title, t.TrackNumber, t.Duration, t.Disc,
    a.Name, l.Title
  from CoreTracks as t
    join CoreArtists as a on t.ArtistID = a.ArtistID
    join CoreAlbums as l on t.AlbumID = l.AlbumID
  where t.Rating > 2
);
my $track_s = $dbh->prepare($track_q);
$track_s->execute;
my ($rows, $tracks, $links) = (0, 0, 0);
my %gm;
while (my $row = $track_s->fetchrow_arrayref) {
    ++$rows;
    my %track;
    @track{qw(id uri title n time disc artist album)} = @$row;
    # make sure it is a local music file
    my $prefix = "file://$ENV{HOME}/Music";
    next unless $track{uri} =~ m/^$prefix/o;
    next if $track{uri} =~ m/\.pdf$/; # skip pdf files
    if ($track{uri} !~ m/\.(ogg|flac|mp3|m4a)$/i) {
        warn("$pkg: not a supported audio file, skipping: $track{uri}\n");
        next;
    }
    ++$tracks;

    # translate uri to file system paths
    my $src = uri_unescape($track{uri});
    $src =~ s,^$prefix,$archive/banshee/Music,;
    my $dest = $src;
    $dest =~ s,banshee/,gm/Google,;
    # store dest for later use
    $gm{$dest} = 1;

    # do not link dest files that exist or src files that do not
    next if -f $dest;
    if (!-f $src) {
        warn("$pkg: original file does not exist: $src");
        next;
    }

    # FIXME remove when not testing
    $dryrun = 1; next;

    # create path to dest
    my $destdir = dirname($dest);
    make_path($destdir) unless $dryrun;

    # link in the file
    if ($dryrun || (system('ln', $src, $dest) == 0)) {
        ++$links;
        &status("created $dest");
    }
    else {
        warn("$pkg: failed to link $src to $dest");
        next;
    }
}
$track_s->finish;
$dbh->disconnect;

# make sure no downgraded/changed/deleted songs remain in GoogleMusic
my $delete = 0;
find(\&track_check, "$archive/gm/GoogleMusic");
finddepth(\&empty_dir, "$archive/gm/GoogleMusic");

# report what was done
&status("found $rows rows, $tracks tracks, created $links links, deleted $delete tracks");

exit(0);

sub status {
    my ($msg) = @_;
    return 0 if $quiet;
    return print("$pkg: $msg\n");
}

sub track_check {
    my $track = $File::Find::name;
    return unless -f $track;
    if (!exists($gm{$track})) {
        if ($dryrun || unlink($track)) {
            ++$delete;
            print("$pkg: removed $track\n") unless $quiet;
        }
        else {
            warn("$pkg: failed to remove $track");
            return;
        }
    }
    return;
}

sub empty_dir {
    my $dir = $File::Find::name;
    if (-d $dir) {
        # see if director is empty
        my $dh = IO::Dir->new($dir);
        if (!defined($dh)) {
            warn("$pkg: failed to open directory $dir");
            return;
        }
        while (defined(my $f = $dh->read())) {
            if ($f ne '.' && $f ne '..') {
                return;
            }
        }
        $dh->close;
        # remove the empty directory
        if ($dryrun || rmdir($dir)) {
            print("$pkg: removed empty directory $dir\n") unless $quiet;
        }
        else {
            warn("$pkg: failed to remove empty directory $dir");
            return;
        }
    }
    return;
}

__END__

=pod

=head1 NAME

banshee-gm - Synchronize good Music to GoogleMusic

=head1 SYNOPSIS

B<gxfer-upload> [OPTIONS]... HTML

=head1 DESCRIPTION

This programs reads a Banshee database and hard links the songs with
ratings greater than two into the ~/GoogleMusic directory.  It also
removes any files under GoogleMusic that are not in the Banshee database
with more than two stars.

=head1 OPTIONS

If an argument to a long option is mandatory, it is also mandatory for
the corresponding short option; the same is true for optional arguments.

=over 4

=item --dry-run

Do not actually create or delete any files in the GoogleMusic directory.

=item --help

Display a brief description and listing of all available options.

=item --quiet

Do not print out progress messages.

=item --version

Output version information and exit.

=item --

Terminate option processing.  This option is useful when file names
begin with a dash (-).

=back

=head1 EXAMPLES

=head1 BUGS

Please email the author if you identify a bug.

=head1 SEE ALSO

sqlite3(1), banshee(1)

=head1 AUTHOR

David Dooling <banjo@users.sourceforge.net>

=cut
