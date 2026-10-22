type Pose = 'standing' | 'wave' | 'profile' | 'turn';

export default function Mascot({pose, className = ''}: {pose: Pose; className?: string}) {
  return <img className={'catalina-mascot mascot-' + pose + ' ' + className}
    src="/brand/catalina-feminine.png" alt=""
    loading="lazy" decoding="async" width={1280} height={1280}/>;
}
