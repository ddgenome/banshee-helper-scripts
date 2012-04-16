#! /usr/bin/env perl
# list recently played or recently added
use warnings;
use strict;

use DBI;
use File::Basename;
use File::Find;
use File::Path qw(make_path);
use Getopt::Long;
use IO::Dir;
use Pod::Usage;
use URI::Escape;

my $pkg = 'banshee-recent';
my $version = '0.1';

# process command line options
my ($played, $limit) = (1, 10);
unless (GetOptions(help => sub { &pod2usage(-exitval => 0) },
                   added => sub { $played = 0 },
                   'limit=i' => \$limit,
                   played => sub { $played = 1 },
                   version => sub { print "$pkg $version\n"; exit 0 }))
{
    warn("Try `$pkg --help' for more information.\n");
    exit(1);
}

# connect to database
my $banshee_db = "$ENV{HOME}/.config/banshee-1/banshee.db";
my $dbh = DBI->connect(
    "dbi:SQLite:dbname=$banshee_db",
    '', '', { RaiseError => 1, AutoCommit => 0 }
);
if (!defined($dbh)) {
    warn("$pkg: failed to connect to banshee db: $banshee_db");
    exit(1);
}

# get tracks from library
my $stamp = ($played) ? 'LastPlayedStamp' : 'DateAddedStamp';
my $track_q = qq(
  select TrackID, Uri
  from CoreTracks
  order by $stamp desc
  limit $limit
);
my $track_s = $dbh->prepare($track_q);
$track_s->execute;
while (my $row = $track_s->fetchrow_arrayref) {
    my ($id, $uri) = @$row;

    # make sure path is sane and clean it
    my $prefix = "file://$ENV{HOME}/Music";
    if ($uri !~ m/^$prefix/) {
        warn("$pkg: unknown path: $uri");
        next;
    }
    $uri =~ s/^$prefix/./;

    # translate uri to file system paths
    my $path = uri_unescape($uri);

    # output
    print("$path\n");
}
$track_s->finish;
$dbh->disconnect;

exit(0);

__END__

=pod

=head1 NAME

banshee-recent - output recently played music

=head1 SYNOPSIS

B<banshee-recent> [OPTIONS]...

=head1 DESCRIPTION

This programs reads a Banshee database and outputs the ten most recently
played tracks.  Alternatively, the most recently added tracks can be output.
The number of songs can be changed.

=head1 OPTIONS

If an argument to a long option is mandatory, it is also mandatory for
the corresponding short option; the same is true for optional arguments.

=over 4

=item --added

Output the most recently added tracks rather than the most recently played.

=item --help

Display a brief description and listing of all available options.

=item --limit=N

Output the most recent N tracks [N=10 default].

=item --played

Output the most recently played tracks [default].

=item --version

Output version information and exit.

=item --

Terminate option processing.  This option is useful when file names
begin with a dash (-).

=back

=head1 EXAMPLES

To see the 30 most recently added tracks, run

  $ banshee-recent --added --limit=30

=head1 BUGS

Please email the author if you identify a bug.

=head1 SEE ALSO

sqlite3(1), banshee(1)

=head1 AUTHOR

David Dooling <banjo@users.sourceforge.net>

=cut
