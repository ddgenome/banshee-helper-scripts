#! /usr/bin/env perl
# correct uri of tracks when they get out of sync
# one time hack, do not use without checking
use warnings;
use strict;

use DBI;
use Getopt::Long;

my $pkg = 'banshee-uri';
my $version = '0.1';

my ($check);
unless (GetOptions(help => sub { print "$pkg [OPTIONS]...\n" },
                   check => \$check,
                   version => sub { print "$pkg $version\n" }
                  ))
{
    warn("Try `$pkg --help' for more information.\n");
    exit(1);
}

# connect to database
my $dbh = DBI->connect(
    "dbi:SQLite:dbname=banshee.db",
    '', '', { RaiseError => 1, AutoCommit => 0 }
);

my $track_q = q(
  select t.TrackID, t.Uri
  from CoreTracks as t
  where AlbumID = 1154
    and Uri like '%/00.%'
);
my $track_s = $dbh->prepare($track_q);

my $update_q = q(
  update CoreTracks
  set Uri = ?
  where TrackID = ?
);
my $update_s = $dbh->prepare($update_q);

# get tracks and start loop
$track_s->execute;
my $tracks = 0;
while (my $row = $track_s->fetchrow_arrayref) {
    ++$tracks;
    my ($id, $old_uri) = @$row;
    # fix Uri
    my $uri = $old_uri;
    $uri =~ s/00\.%20//;
    # update track
    if ($check) {
        print("$pkg: $id:$old_uri => $uri\n");
    }
    else {
        $update_s->execute($uri, $id);
    }
}
print("$pkg: Updated $tracks tracks\n");

$track_s->finish;
$update_s->finish;
$dbh->commit;
$dbh->disconnect;

exit(0);
