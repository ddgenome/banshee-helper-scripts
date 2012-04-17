#! /usr/bin/env perl
# determine if any tracks are missing from library or file system
use warnings;
use strict;

use Cwd;
use DBI;
use File::Find;
use Getopt::Long;
use Pod::Usage;
use URI::Escape;

my $pkg = 'banshee-diff';
my $version = '0.1';

unless (GetOptions(help => sub { &pod2usage(-exitval => 0) },
                   version => sub { print "$pkg $version\n"; exit(0) }
                  ))
{
    warn("Try `$pkg --help' for more information.\n");
    exit(1);
}

# connect to database
my $dbh = DBI->connect(
    "dbi:SQLite:dbname=$ENV{HOME}/.config/banshee-1/banshee.db",
    '', '', { RaiseError => 1, AutoCommit => 0 }
);

# get tracks from library
my $track_q = q(
  select TrackID, Uri
  from CoreTracks
);
my $track_s = $dbh->prepare($track_q);
$track_s->execute;

# loop through banshee tracks
my ($tracks, $missing) = (0, 0);
my %b_tracks;
while (my $row = $track_s->fetchrow_arrayref) {
    my ($id, $uri) = @$row;
    # make sure it is a local music file
    my $prefix = "file://$ENV{HOME}/Music";
    next unless $uri =~ m/^$prefix/o;
    ++$tracks;

    # convert uri into file system path
    my $path = uri_unescape($uri);
    # remove protocol specification
    $path =~ s,^file://,,;

    if (! -f $path) {
        ++$missing;
        warn("$pkg: missing: $path\n")
    }

    # save for later use
    $b_tracks{$path} = 1;
}
print("$pkg: checked $tracks tracks, $missing missing\n");

# find files not in database
my ($files, $extra) = (0, 0);
# account for symbolic links
my $music_path = "$ENV{HOME}/Music";
my $music_abs_path = Cwd::abs_path($music_path);
# loop through files
find(\&check_track, $music_abs_path);
print("$pkg: checked $files files, $extra extra\n");

$track_s->finish;
$dbh->commit;
$dbh->disconnect;

exit(0);

# see if a file exists in the banshee database (using the hash)
sub check_track {
    my $path = $File::Find::name;
    # only check files (not directories)
    return unless -f $path;
    # skip non-music files
    return unless $path =~ m/\.(flac|m4a|mp3|ogg)$/i;
    ++$files;
    # account for symbolic links
    if ($music_path ne $music_abs_path) {
        $path =~ s/$music_abs_path/$music_path/;
    }
    if (!exists($b_tracks{$path})) {
        ++$extra;
        warn("$pkg: extra: $path\n");
    }
    return;
}

__END__

=pod

=head1 NAME

banshee-diff - find differences between Banshee database and file system

=head1 SYNOPSIS

B<banshee-diff> [OPTIONS]...

=head1 DESCRIPTION

This programs reads a Banshee database and the file system and
determines files that are either missing from the database or missing
from the file system.  It makes not attempt to correct the errors.

=head1 OPTIONS

If an argument to a long option is mandatory, it is also mandatory for
the corresponding short option; the same is true for optional arguments.

=over 4

=item --help

Display a brief description and listing of all available options.

=item --version

Output version information and exit.

=item --

Terminate option processing.  This option is useful when file names
begin with a dash (-).

=back

=head1 EXAMPLES

To see what would be done without any files actually being created or
destroyed, run

  $ banshee-gm --dry-run --verbose

=head1 BUGS

Please email the author if you identify a bug.

=head1 SEE ALSO

sqlite3(1), banshee(1)

=head1 AUTHOR

David Dooling <banjo@users.sourceforge.net>

=cut
