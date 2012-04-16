#! /usr/bin/env perl
# determine if any tracks are missing from library or file system
use warnings;
use strict;

use DBI;
use Getopt::Long;

my $pkg = 'banshee-tracks';
my $version = '0.1';

unless (GetOptions(help => sub { print "$pkg [OPTIONS]...\n" },
                   version => sub { print "$pkg $version\n" }
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
my $tracks = 0;
while (my $row = $track_s->fetchrow_arrayref) {
    ++$tracks;
    my ($id, $uri) = @$row;
    # FIXME
}
print("$pkg: Updated $tracks tracks\n");

$track_s->finish;
$dbh->commit;
$dbh->disconnect;

exit(0);
