#! /usr/bin/env perl
# hard links good tracks into google music directory
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

my $pkg = 'banshee-gm';
my $version = '0.4';
my $archive = '/home/archive/ddooling';

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
my $track_q = q(
  select TrackID, Uri
  from CoreTracks
  where Rating > 2
);
my $track_s = $dbh->prepare($track_q);
$track_s->execute;
my $rows = 0;
my $tracks = 0;
my $links = 0;
my %gm;
while (my $row = $track_s->fetchrow_arrayref) {
    ++$rows;
    my ($id, $uri) = @$row;
    # make sure it is a local music file
    my $prefix = "file://$ENV{HOME}/Music";
    next unless $uri =~ m/^$prefix/;
    next if $uri =~ m/\.pdf$/; # skip pdf files
    if ($uri !~ m/\.(ogg|flac|mp3|m4a)$/i) {
        warn("$pkg: not a supported audio file, skipping: $uri\n");
        next;
    }
    ++$tracks;

    # translate uri to file system paths
    my $src = uri_unescape($uri);
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
    return 1 if $quiet;
    chomp($msg);
    return print("$pkg: $msg\n");
}

sub track_check {
    my $track = $File::Find::name;
    return unless -f $track;
    if (!exists($gm{$track})) {
        if ($dryrun || unlink($track)) {
            ++$delete;
            &status("removed $track");
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
            &status("removed empty directory $dir");
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

B<banshee-gm> [OPTIONS]...

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

Do not print out file creation or deletion events.

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
