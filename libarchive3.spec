%if 0%{?rhel} < 7
%{!?__global_ldflags: %global __global_ldflags -Wl,-z,relro}
%endif

Name:           libarchive3
Version:        3.3.1
Release:        1%{?dist}
Summary:        A library for handling streaming archive formats

License:        BSD
URL:            http://www.libarchive.org/
Source0:        http://www.libarchive.org/downloads/libarchive-%{version}.tar.gz

# CMake sets 15 as soname unlike libarchive on Fedora by using GNU libtools
# I'm patching CMakeLists.txt file to be contiguos with the Fedora's package
# https://github.com/libarchive/libarchive/issues/749
Patch0:        %{name}-fix_soname.patch

# Upstream commit 1bfa37818f5e6
Patch1:        libarchive-3.3.1-cpio-getid.patch

BuildRequires: bison
BuildRequires: sharutils
BuildRequires: zlib-devel
BuildRequires: bzip2-devel
BuildRequires: xz-devel
BuildRequires: lzo-devel
BuildRequires: e2fsprogs-devel
BuildRequires: libacl-devel
BuildRequires: libattr-devel
BuildRequires: openssl-devel
BuildRequires: libxml2-devel
BuildRequires: valgrind
BuildRequires: intltool
%if 0%{?fedora}
BuildRequires: autoconf
BuildRequires: libtool
%else
BuildRequires: cmake3
%endif

%description
Libarchive is a programming library that can create and read several different
streaming archive formats, including most popular tar variants, several cpio
formats, and both BSD and GNU ar variants. It can also write shar archives and
read ISO9660 CDROM images and ZIP archives.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%package -n     bsdtar3
Summary:        Manipulate tape archives
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n bsdtar3
The bsdtar package contains standalone bsdtar utility split off regular
libarchive packages.


%package -n     bsdcpio3
Summary:        Copy files to and from archives
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n bsdcpio3
The bsdcpio package contains standalone bsdcpio utility split off regular
libarchive packages.

%package -n     bsdcat3
Summary:        Expand files to standard output
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n bsdcat3
The bsdcat3 package contains standalone bsdcat utility split off regular
libarchive packages.


%prep
%setup -qn libarchive-%{version}
%if 0%{?rhel}
%patch0 -p0
%endif
%patch1 -p1

%build
%if 0%{?fedora}
build/autogen.sh
# https://github.com/libarchive/libarchive/issues/694
export CFLAGS="%{optflags} -Wno-error=deprecated-declarations"
%configure --disable-static --disable-rpath
%else
export CFLAGS="%{optflags} -Wl,-z,relro"
export LDFLAGS="%{__global_ldflags}"
cmake3 -DENABLE_ICONV:BOOL=OFF \
       -DCMAKE_C_FLAGS_RELEASE:STRING="-DNDEBUG" \
       -DCMAKE_VERBOSE_MAKEFILE:BOOL=ON \
       -DCMAKE_INSTALL_PREFIX:PATH=%{_prefix} \
       -DINCLUDE_INSTALL_DIR:PATH=%{_includedir} \
       -DLIB_INSTALL_DIR:PATH=%{_libdir} \
       -DCMAKE_SKIP_RPATH:BOOL=YES \
       -DBUILD_SHARED_LIBS:BOOL=ON
%endif

%if 0%{?fedora}
# remove rpaths
sed -i 's|^hardcode_libdir_flag_spec=.*|hardcode_libdir_flag_spec=""|g' libtool
sed -i 's|^runpath_var=LD_RUN_PATH|runpath_var=DIE_RPATH_DIE|g' libtool
%endif

test -z "$V" && verbose_make="V=1"
make %{?_smp_mflags} $verbose_make


%install
make install DESTDIR=%{buildroot}

# Rename files, so they don't clash with original libarchive.
for bin in %{buildroot}%{_bindir}/*
do
    mv -fv "${bin}" "${bin}3"
done

for man in $(find %{buildroot}%{_mandir} -type f)
do
    dir=$(dirname "$man")
    name=$(basename "$man" | sed -e 's!\..*$!!g')
    ext=$(basename "$man"  | sed -e 's!^.*\.!!g')
    mv -fv "${man}" "${dir}/${name}3.${ext}"
done

for header in $(find %{buildroot}%{_includedir} -type f)
do
    dir=$(dirname "$header")
    name=$(basename "$header" | sed -e 's!\..*$!!g')
    ext=$(basename "$header"  | sed -e 's!^.*\.!!g')
    mv -fv "${header}" "${dir}/${name}3.${ext}"
done

# cmake variables look ignored
%if 0%{?rhel}
%if %{?__isa_bits:%{__isa_bits}}%{!?__isa_bits:32} == 64
mv -fv %{buildroot}%{_prefix}/lib %{buildroot}%{_libdir}
%endif
%endif

mv -fv %{buildroot}%{_libdir}/libarchive.so %{buildroot}%{_libdir}/libarchive3.so
mv -fv %{buildroot}%{_libdir}/pkgconfig/libarchive.pc \
       %{buildroot}%{_libdir}/pkgconfig/libarchive3.pc
sed -i -e 's!l.*archive!&3!g' %{buildroot}%{_libdir}/pkgconfig/libarchive3.pc

find %{buildroot} -name '*.a' -exec rm -f {} ';'
find %{buildroot} -name '*.la' -exec rm -f {} ';'


%check
run_testsuite()
{
%if 0%{?fedora}
    LD_LIBRARY_PATH=`pwd`/.libs make check -j1
%else
    LD_LIBRARY_PATH=`pwd`/libarchive ctest3 -j1 --force-new-ctest-process -E "test_write_format_xar"
%endif
    res=$?
    echo $res
    if [ $res -ne 0 ]; then
        # error happened - try to extract in koji as much info as possible
        cat test-suite.log
        echo "========================="
        err=`cat test-suite.log | grep "Details for failing tests" | cut -d: -f2`
        for i in $err; do
            find $i -printf "%p\n    ~> a: %a\n    ~> c: %c\n    ~> t: %t\n    ~> %s B\n"
            echo "-------------------------"
            cat $i/*.log
        done
        return 1
    else
        return 0
    fi
}

# On a ppc/ppc64 is some race condition causing 'make check' fail on ppc
# when both 32 and 64 builds are done in parallel on the same machine in
# koji.  Try to run once again if failed.
%ifarch ppc
run_testsuite || run_testsuite
%else
# On ix86 the xar write test may fail.  Running it with valgrind makes it pass.
run_testsuite || valgrind ./libarchive_test
%endif


%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig


%files
%{!?_licensedir:%global license %%doc}
%license COPYING
%doc README.md NEWS
%{_libdir}/libarchive.so.*
%{_mandir}/*/cpio*3.*
%{_mandir}/*/mtree*3.*
%{_mandir}/*/tar*3.*

%files devel
%{_includedir}/*3.h
%{_mandir}/*/archive*3.*
%{_mandir}/*/libarchive*3.*
%{_libdir}/libarchive3.so
%{_libdir}/pkgconfig/libarchive3.pc

%files -n bsdtar3
%{!?_licensedir:%global license %%doc}
%license COPYING
%doc README.md NEWS
%{_bindir}/bsdtar3
%{_mandir}/*/bsdtar*3.*

%files -n bsdcpio3
%{!?_licensedir:%global license %%doc}
%license COPYING
%doc README.md NEWS
%{_bindir}/bsdcpio3
%{_mandir}/*/bsdcpio*3.*

%files -n bsdcat3
%{!?_licensedir:%global license %%doc}
%license COPYING
%doc README.md NEWS
%{_bindir}/bsdcat3
%{_mandir}/*/bsdcat*3.*

%changelog
* Sat Aug 05 2017 Antonio Trande <sagitterATfedoraproject.org> - 3.3.1-1
- Update to 3.3.1
- Drop obsolete patches

* Wed Jul 20 2016 Antonio Trande <sagitterATfedoraproject.org> - 3.2.1-1
- Update to 3.2.1
- Drop old patches
- Make bsdcat3 sub-package
- Use cmake as builder on epel (autogen.sh needs autoconf >= 2.69)
- Use ctest for testing
- Fix bz#1358370

* Mon Mar 07 2016 Björn Esser <fedora@besser82.io> - 3.1.2-1
- initial epel-release (#1315307)
